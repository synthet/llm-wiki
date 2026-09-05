"""Build and query a search index over a wiki.

Prefers SQLite FTS5 for fast full-text ranking (BM25); falls back to a JSON
inverted index when FTS5 is unavailable. Both back-ends expose the same
:class:`SearchResult` shape so callers (CLI, MCP, search engine) don't care
which is in use.

The on-disk index also stores the wikilink graph so search can optionally
expand results by one hop.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .model import content_digest
from .wiki import Wiki

INDEX_DIRNAME = ".llmwiki"
DB_NAME = "index.db"
JSON_NAME = "index.json"

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass
class SearchResult:
    id: str
    title: str
    path: str
    status: str
    type: str
    score: float
    snippet: str = ""
    tags: List[str] = field(default_factory=list)
    matched_via: str = "direct"  # "direct" | "wikilink"

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "path": self.path,
            "status": self.status,
            "type": self.type,
            "score": round(self.score, 6),
            "snippet": self.snippet,
            "tags": self.tags,
            "matched_via": self.matched_via,
        }


def fts5_available() -> bool:
    try:
        con = sqlite3.connect(":memory:")
        con.execute("CREATE VIRTUAL TABLE _t USING fts5(x)")
        con.close()
        return True
    except sqlite3.OperationalError:
        return False


class Index:
    """A search index bound to a wiki root."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.dir = self.root / INDEX_DIRNAME
        self.db_path = self.dir / DB_NAME
        self.json_path = self.dir / JSON_NAME
        self.use_fts = fts5_available()

    # -- build ----------------------------------------------------------------
    def build(self, wiki: Optional[Wiki] = None) -> Dict[str, int]:
        wiki = wiki or Wiki(self.root).load()
        self.dir.mkdir(parents=True, exist_ok=True)
        if self.use_fts:
            n = self._build_fts(wiki)
        else:
            n = self._build_json(wiki)
        return {"pages": n, "backend": 1 if self.use_fts else 0}

    def _page_rows(self, wiki: Wiki):
        for page in wiki.pages:
            rel = wiki.rel(page)
            links = [
                (wiki.resolve_link(l.target).id if wiki.resolve_link(l.target) else None)
                for l in page.links
            ]
            yield {
                "id": page.id,
                "title": page.title,
                "path": rel,
                "status": page.status,
                "type": page.type,
                "tags": page.tags,
                "aliases": page.aliases,
                "text": page.text_for_index(),
                "digest": content_digest(page.raw),
                "links": [x for x in links if x],
            }

    def _build_fts(self, wiki: Wiki) -> int:
        if self.db_path.exists():
            self.db_path.unlink()
        con = sqlite3.connect(self.db_path)
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute(
                """CREATE TABLE pages(
                    id TEXT PRIMARY KEY, title TEXT, path TEXT, status TEXT,
                    type TEXT, tags TEXT, digest TEXT, links TEXT)"""
            )
            con.execute(
                "CREATE VIRTUAL TABLE fts USING fts5("
                "title, tags, body, pid UNINDEXED, tokenize='porter unicode61')"
            )
            n = 0
            for row in self._page_rows(wiki):
                con.execute(
                    "INSERT INTO pages VALUES(?,?,?,?,?,?,?,?)",
                    (
                        row["id"], row["title"], row["path"], row["status"],
                        row["type"], json.dumps(row["tags"]), row["digest"],
                        json.dumps(row["links"]),
                    ),
                )
                con.execute(
                    "INSERT INTO fts(title, tags, body, pid) VALUES(?,?,?,?)",
                    (row["title"], " ".join(row["tags"] + row["aliases"]), row["text"], row["id"]),
                )
                n += 1
            con.commit()
            return n
        finally:
            con.close()

    def _build_json(self, wiki: Wiki) -> int:
        docs = {}
        df: Dict[str, int] = {}
        for row in self._page_rows(wiki):
            tokens = _tokenize(row["title"] + " " + " ".join(row["tags"]) + " " + row["text"])
            tf: Dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            for t in tf:
                df[t] = df.get(t, 0) + 1
            docs[row["id"]] = {
                "title": row["title"], "path": row["path"], "status": row["status"],
                "type": row["type"], "tags": row["tags"], "digest": row["digest"],
                "links": row["links"], "tf": tf, "len": len(tokens),
                "text": row["text"][:2000],
            }
        payload = {"version": 1, "docs": docs, "df": df, "N": len(docs)}
        self.json_path.write_text(json.dumps(payload), encoding="utf-8")
        return len(docs)

    # -- status ---------------------------------------------------------------
    def exists(self) -> bool:
        return (self.db_path.exists() and self.use_fts) or self.json_path.exists()

    def backend_name(self) -> str:
        if self.db_path.exists() and self.use_fts:
            return "sqlite-fts5"
        if self.json_path.exists():
            return "json-inverted"
        return "none"

    # -- query ----------------------------------------------------------------
    def search(self, query: str, limit: int = 10, status: Optional[str] = None,
               type_: Optional[str] = None) -> List[SearchResult]:
        if self.db_path.exists() and self.use_fts:
            return self._search_fts(query, limit, status, type_)
        if self.json_path.exists():
            return self._search_json(query, limit, status, type_)
        raise FileNotFoundError("no index found; run `llmwiki index` first")

    def _search_fts(self, query, limit, status, type_) -> List[SearchResult]:
        con = sqlite3.connect(self.db_path)
        try:
            con.row_factory = sqlite3.Row
            match = _fts_query(query)
            sql = (
                "SELECT p.id AS id, p.title AS title, p.path AS path, p.status AS status, "
                "p.type AS type, p.tags AS tags, "
                "snippet(fts, 2, '[', ']', ' … ', 12) AS snip, bm25(fts) AS rank "
                "FROM fts JOIN pages p ON p.id = fts.pid WHERE fts MATCH ? "
            )
            params: List = [match]
            if status:
                sql += "AND p.status = ? "
                params.append(status)
            if type_:
                sql += "AND p.type = ? "
                params.append(type_)
            sql += "ORDER BY rank LIMIT ?"
            params.append(limit)
            rows = con.execute(sql, params).fetchall()
            out = []
            for r in rows:
                out.append(SearchResult(
                    id=r["id"], title=r["title"], path=r["path"], status=r["status"],
                    type=r["type"], score=-float(r["rank"]),
                    snippet=(r["snip"] or "").strip(), tags=json.loads(r["tags"] or "[]"),
                ))
            return out
        finally:
            con.close()

    def _search_json(self, query, limit, status, type_) -> List[SearchResult]:
        payload = json.loads(self.json_path.read_text(encoding="utf-8"))
        docs, df, N = payload["docs"], payload["df"], max(payload["N"], 1)
        q_tokens = _tokenize(query)
        avg_len = sum(d["len"] for d in docs.values()) / max(len(docs), 1) or 1
        k1, b = 1.5, 0.75
        scored = []
        for pid, d in docs.items():
            if status and d["status"] != status:
                continue
            if type_ and d["type"] != type_:
                continue
            score = 0.0
            for t in q_tokens:
                if t not in d["tf"]:
                    continue
                idf = math.log(1 + (N - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5))
                tf = d["tf"][t]
                denom = tf + k1 * (1 - b + b * d["len"] / avg_len)
                score += idf * (tf * (k1 + 1)) / denom
            if score > 0:
                scored.append((score, pid, d))
        scored.sort(key=lambda x: -x[0])
        out = []
        for score, pid, d in scored[:limit]:
            out.append(SearchResult(
                id=pid, title=d["title"], path=d["path"], status=d["status"],
                type=d["type"], score=score, tags=d["tags"],
                snippet=_json_snippet(d["text"], q_tokens),
            ))
        return out

    def links_of(self, page_id: str) -> List[str]:
        if self.db_path.exists() and self.use_fts:
            con = sqlite3.connect(self.db_path)
            try:
                row = con.execute("SELECT links FROM pages WHERE id=?", (page_id,)).fetchone()
                return json.loads(row[0]) if row else []
            finally:
                con.close()
        if self.json_path.exists():
            payload = json.loads(self.json_path.read_text(encoding="utf-8"))
            d = payload["docs"].get(page_id)
            return d["links"] if d else []
        return []

    def meta(self, page_id: str) -> Optional[dict]:
        if self.db_path.exists() and self.use_fts:
            con = sqlite3.connect(self.db_path)
            try:
                con.row_factory = sqlite3.Row
                r = con.execute("SELECT * FROM pages WHERE id=?", (page_id,)).fetchone()
                if not r:
                    return None
                return {"id": r["id"], "title": r["title"], "path": r["path"],
                        "status": r["status"], "type": r["type"],
                        "tags": json.loads(r["tags"] or "[]")}
            finally:
                con.close()
        if self.json_path.exists():
            payload = json.loads(self.json_path.read_text(encoding="utf-8"))
            d = payload["docs"].get(page_id)
            if not d:
                return None
            return {"id": page_id, "title": d["title"], "path": d["path"],
                    "status": d["status"], "type": d["type"], "tags": d["tags"]}
        return None


def _fts_query(query: str) -> str:
    """Turn a user query into a safe FTS5 MATCH expression.

    Quotes each token to avoid FTS5 syntax errors and OR-combines them so
    partial matches still rank; a trailing ``*`` gives prefix search.
    """
    tokens = _TOKEN_RE.findall(query.lower())
    if not tokens:
        return '""'
    return " OR ".join(f'"{t}"*' for t in tokens)


def _json_snippet(text: str, q_tokens: List[str], width: int = 160) -> str:
    low = text.lower()
    for t in q_tokens:
        idx = low.find(t)
        if idx >= 0:
            start = max(0, idx - width // 2)
            end = min(len(text), start + width)
            frag = text[start:end].strip()
            return ("… " if start > 0 else "") + frag + (" …" if end < len(text) else "")
    return text[:width].strip()
