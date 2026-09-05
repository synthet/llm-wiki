"""High-level operations shared by the CLI and the MCP server.

Each function takes a wiki ``root`` and returns plain JSON-serialisable data,
so the CLI can print it and the MCP server can return it as tool output with no
divergence in behaviour.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from . import lint as _lint
from .index import Index
from .model import Page
from .search import search as _search
from .wiki import Wiki


def _load(root: Path) -> Wiki:
    return Wiki(root).load()


def build_index(root: Path) -> Dict[str, Any]:
    wiki = _load(root)
    idx = Index(root)
    result = idx.build(wiki)
    return {
        "pages_indexed": result["pages"],
        "backend": idx.backend_name(),
        "index_dir": str(idx.dir),
    }


def search(root: Path, query: str, limit: int = 10, status: Optional[str] = None,
           type_: Optional[str] = None, expand: bool = False) -> Dict[str, Any]:
    results = _search(root, query, limit=limit, status=status, type_=type_, expand=expand)
    return {"query": query, "count": len(results), "results": [r.as_dict() for r in results]}


def validate(root: Path, strict: bool = False) -> Dict[str, Any]:
    wiki = _load(root)
    issues = _lint.lint(wiki, strict=strict)
    counts = _lint.summarize(issues)
    return {
        "root": str(Path(root).resolve()),
        "pages": len(wiki),
        "ok": counts["error"] == 0,
        "counts": counts,
        "issues": [i.as_dict() for i in issues],
    }


def stats(root: Path) -> Dict[str, Any]:
    wiki = _load(root)
    by_status: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    total_claims = 0
    claims_with_evidence = 0
    total_sources = 0
    total_links = 0
    broken_links = 0
    orphans: List[str] = []
    for page in wiki.pages:
        by_status[page.status] = by_status.get(page.status, 0) + 1
        by_type[page.type] = by_type.get(page.type, 0) + 1
        total_sources += len(page.sources)
        for claim in page.claims:
            total_claims += 1
            if claim.get("evidence"):
                claims_with_evidence += 1
        for link in page.links:
            total_links += 1
            if wiki.resolve_link(link.target) is None:
                broken_links += 1
        if page.type in ("entity", "topic") and not wiki.backlinks(page):
            orphans.append(wiki.rel(page))
    coverage = (claims_with_evidence / total_claims) if total_claims else None
    idx = Index(root)
    return {
        "pages": len(wiki),
        "by_status": by_status,
        "by_type": by_type,
        "claims": total_claims,
        "claims_with_evidence": claims_with_evidence,
        "citation_coverage": round(coverage, 3) if coverage is not None else None,
        "sources": total_sources,
        "wikilinks": total_links,
        "broken_wikilinks": broken_links,
        "orphan_pages": orphans,
        "index_backend": idx.backend_name(),
        "index_present": idx.exists(),
    }


def get_page(root: Path, ref: str, body: bool = True) -> Dict[str, Any]:
    wiki = _load(root)
    page = wiki.get(ref)
    if page is None:
        return {"found": False, "ref": ref}
    out: Dict[str, Any] = {
        "found": True,
        "id": page.id,
        "title": page.title,
        "path": wiki.rel(page),
        "type": page.type,
        "status": page.status,
        "tags": page.tags,
        "aliases": page.aliases,
        "sources": page.sources,
        "claims": page.claims,
        "outbound_links": [wiki.rel(p) for p in wiki.outbound(page)],
        "backlinks": [wiki.rel(p) for p in wiki.backlinks(page)],
    }
    if body:
        out["body"] = page.body
    return out


def list_pages(root: Path, status: Optional[str] = None, type_: Optional[str] = None,
               tag: Optional[str] = None) -> Dict[str, Any]:
    wiki = _load(root)
    items = []
    for page in wiki.pages:
        if status and page.status != status:
            continue
        if type_ and page.type != type_:
            continue
        if tag and tag not in page.tags:
            continue
        items.append({
            "id": page.id, "title": page.title, "path": wiki.rel(page),
            "type": page.type, "status": page.status, "tags": page.tags,
        })
    return {"count": len(items), "pages": items}


def backlinks(root: Path, ref: str) -> Dict[str, Any]:
    wiki = _load(root)
    page = wiki.get(ref)
    if page is None:
        return {"found": False, "ref": ref}
    return {
        "found": True,
        "id": page.id,
        "title": page.title,
        "backlinks": [{"title": p.title, "path": wiki.rel(p)} for p in wiki.backlinks(page)],
        "outbound": [{"title": p.title, "path": wiki.rel(p)} for p in wiki.outbound(page)],
    }
