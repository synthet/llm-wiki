"""SQLite canonical repository and deterministic schema migration."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .domain import SCHEMA_VERSION, canonical_json, utc_now
from .errors import error

MIGRATION_1 = [
    "CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)",
    "CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    """CREATE TABLE sources(
        id TEXT PRIMARY KEY, source_key TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
        original_uri TEXT NOT NULL, media_type TEXT NOT NULL, rights TEXT NOT NULL DEFAULT 'unknown',
        created_at TEXT NOT NULL, current_revision_id TEXT)""",
    """CREATE TABLE source_revisions(
        id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id), digest TEXT NOT NULL,
        content_path TEXT NOT NULL, byte_size INTEGER NOT NULL, acquired_at TEXT NOT NULL,
        parser_version TEXT NOT NULL, config_digest TEXT NOT NULL, extracted_text TEXT NOT NULL,
        extraction_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ready',
        UNIQUE(source_id, digest))""",
    "CREATE UNIQUE INDEX source_revision_identity ON source_revisions(id, digest)",
    """CREATE TABLE entities(
        id TEXT PRIMARY KEY, canonical_name TEXT NOT NULL, slug TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL)""",
    """CREATE TABLE entity_aliases(
        entity_id TEXT NOT NULL REFERENCES entities(id), alias TEXT NOT NULL,
        normalized_alias TEXT NOT NULL, PRIMARY KEY(entity_id, normalized_alias))""",
    "CREATE INDEX aliases_lookup ON entity_aliases(normalized_alias)",
    """CREATE TABLE claims(
        id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entities(id), created_at TEXT NOT NULL)""",
    """CREATE TABLE claim_revisions(
        id TEXT PRIMARY KEY, claim_id TEXT NOT NULL REFERENCES claims(id), text TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('candidate','reviewed','disputed','stale','superseded','retracted')),
        created_at TEXT NOT NULL, supersedes_revision_id TEXT REFERENCES claim_revisions(id),
        content_digest TEXT NOT NULL, is_current INTEGER NOT NULL CHECK(is_current IN (0,1)))""",
    "CREATE INDEX claim_revisions_current ON claim_revisions(claim_id, is_current, status)",
    """CREATE TABLE evidence(
        id TEXT PRIMARY KEY, claim_revision_id TEXT NOT NULL REFERENCES claim_revisions(id),
        source_revision_id TEXT NOT NULL REFERENCES source_revisions(id), locator_json TEXT NOT NULL,
        quote TEXT NOT NULL, created_at TEXT NOT NULL)""",
    "CREATE INDEX evidence_revision ON evidence(source_revision_id)",
    """CREATE TABLE contradictions(
        id TEXT PRIMARY KEY, left_claim_revision_id TEXT NOT NULL REFERENCES claim_revisions(id),
        right_claim_revision_id TEXT NOT NULL REFERENCES claim_revisions(id), status TEXT NOT NULL,
        reason TEXT NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(left_claim_revision_id, right_claim_revision_id))""",
    """CREATE TABLE dependencies(
        claim_revision_id TEXT NOT NULL REFERENCES claim_revisions(id),
        source_revision_id TEXT NOT NULL REFERENCES source_revisions(id),
        PRIMARY KEY(claim_revision_id, source_revision_id))""",
    """CREATE TABLE review_events(
        id TEXT PRIMARY KEY, claim_revision_id TEXT NOT NULL REFERENCES claim_revisions(id),
        action TEXT NOT NULL, reviewer TEXT NOT NULL, note TEXT NOT NULL,
        before_status TEXT NOT NULL, after_status TEXT NOT NULL, created_at TEXT NOT NULL)""",
    """CREATE TABLE compilation_runs(
        id TEXT PRIMARY KEY, mode TEXT NOT NULL, status TEXT NOT NULL, state_version INTEGER NOT NULL,
        provider TEXT, model TEXT, prompt_digest TEXT NOT NULL, config_digest TEXT NOT NULL,
        input_revisions_json TEXT NOT NULL, request_json TEXT, result_json TEXT,
        usage_json TEXT, created_at TEXT NOT NULL, completed_at TEXT)""",
    """CREATE TABLE document_nodes(
        id TEXT PRIMARY KEY, source_revision_id TEXT NOT NULL REFERENCES source_revisions(id),
        parent_id TEXT REFERENCES document_nodes(id), depth INTEGER NOT NULL,
        document_order INTEGER NOT NULL, heading TEXT NOT NULL, summary TEXT,
        locator_json TEXT NOT NULL, content_digest TEXT NOT NULL, token_estimate INTEGER NOT NULL,
        UNIQUE(source_revision_id, document_order))""",
    "CREATE INDEX nodes_revision_parent ON document_nodes(source_revision_id, parent_id, document_order)",
    """CREATE TABLE retrieval_traces(
        id TEXT PRIMARY KEY, query TEXT NOT NULL, method TEXT NOT NULL, backend TEXT NOT NULL,
        selected_nodes_json TEXT NOT NULL, decision_summary TEXT NOT NULL,
        result_json TEXT NOT NULL, created_at TEXT NOT NULL)""",
    """CREATE TABLE render_state(
        page_path TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entities(id),
        canonical_digest TEXT NOT NULL, file_digest TEXT NOT NULL, rendered_at TEXT NOT NULL)""",
    """CREATE TABLE jobs(
        id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL,
        idempotency_key TEXT, request_json TEXT NOT NULL, result_json TEXT, error_json TEXT,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(kind, idempotency_key))""",
    "INSERT INTO meta(key, value) VALUES('canonical_state_version', '0')",
    "INSERT INTO meta(key, value) VALUES('search_index_state_version', '0')",
    "INSERT INTO meta(key, value) VALUES('search_index_backend', 'pending')",
]

EXPORT_TABLES = (
    "sources",
    "source_revisions",
    "entities",
    "entity_aliases",
    "claims",
    "claim_revisions",
    "evidence",
    "contradictions",
    "dependencies",
    "review_events",
    "compilation_runs",
    "document_nodes",
    "retrieval_traces",
    "render_state",
    "jobs",
)


class Store:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.db_path, timeout=30)
        try:
            con.execute("PRAGMA foreign_keys=ON")
            has_migrations = con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            ).fetchone()
            current = (
                con.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0]
                if has_migrations
                else 0
            )
            if current > SCHEMA_VERSION:
                raise error(
                    "schema_too_new",
                    "Database schema is newer than this llmwiki version.",
                    found=current,
                    supported=SCHEMA_VERSION,
                )
            if current >= 1:
                metadata = {
                    row[0]
                    for row in con.execute(
                        "SELECT key FROM meta WHERE key IN ('search_index_state_version', 'search_index_backend')"
                    )
                }
                index_tables = {
                    row[0]
                    for row in con.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('claim_fts', 'node_fts')"
                    )
                }
                backend = con.execute(
                    "SELECT value FROM meta WHERE key='search_index_backend'"
                ).fetchone()
                if metadata == {"search_index_state_version", "search_index_backend"} and (
                    index_tables == {"claim_fts", "node_fts"} or (backend and backend[0] == "python-lexical")
                ):
                    return
            con.execute("PRAGMA journal_mode=WAL")
            if current < 1:
                con.execute("BEGIN IMMEDIATE")
                try:
                    for statement in MIGRATION_1:
                        con.execute(statement)
                    con.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)",
                        (1, utc_now()),
                    )
                    con.commit()
                except Exception:
                    con.rollback()
                    raise
            con.execute("INSERT OR IGNORE INTO meta(key, value) VALUES('search_index_state_version', '-1')")
            con.execute("INSERT OR IGNORE INTO meta(key, value) VALUES('search_index_backend', 'pending')")
            try:
                con.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS claim_fts USING fts5("
                    "id UNINDEXED, text, entity_name, tokenize='porter unicode61')"
                )
                con.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS node_fts USING fts5("
                    "id UNINDEXED, heading, content, tokenize='porter unicode61')"
                )
                backend = "sqlite-fts5"
            except sqlite3.OperationalError:
                backend = "python-lexical"
            con.execute("UPDATE meta SET value=? WHERE key='search_index_backend'", (backend,))
            con.commit()
        finally:
            con.close()

    def connect(self) -> sqlite3.Connection:
        self.initialize()
        con = sqlite3.connect(self.db_path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=30000")
        return con

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        con = self.connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    @contextmanager
    def reader(self) -> Iterator[sqlite3.Connection]:
        con = self.connect()
        try:
            yield con
        finally:
            con.close()

    @staticmethod
    def new_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def state_version(con: sqlite3.Connection) -> int:
        row = con.execute("SELECT value FROM meta WHERE key='canonical_state_version'").fetchone()
        return int(row[0])

    @staticmethod
    def bump_state(con: sqlite3.Connection) -> int:
        value = Store.state_version(con) + 1
        con.execute("UPDATE meta SET value=? WHERE key='canonical_state_version'", (str(value),))
        return value

    def rows(self, table: str, *, order_by: str = "rowid") -> list[dict[str, Any]]:
        if table not in EXPORT_TABLES and table not in {"schema_migrations", "meta"}:
            raise ValueError(f"Unsupported table: {table}")
        with self.reader() as con:
            return [dict(row) for row in con.execute(f"SELECT * FROM {table} ORDER BY {order_by}")]

    def dump(self) -> dict[str, Any]:
        with self.reader() as con:
            result: dict[str, Any] = {}
            for table in EXPORT_TABLES:
                columns = [row[1] for row in con.execute(f"PRAGMA table_info({table})")]
                ordering = ", ".join(columns) if columns else "rowid"
                result[table] = [dict(row) for row in con.execute(f"SELECT * FROM {table} ORDER BY {ordering}")]
            return result

    def create_job(self, kind: str, request: dict[str, Any], idempotency_key: str | None = None) -> dict[str, Any]:
        with self.transaction() as con:
            if idempotency_key:
                existing = con.execute(
                    "SELECT * FROM jobs WHERE kind=? AND idempotency_key=?",
                    (kind, idempotency_key),
                ).fetchone()
                if existing:
                    return _job_dict(existing)
            now = utc_now()
            job_id = self.new_id()
            con.execute(
                """INSERT INTO jobs(id, kind, status, idempotency_key, request_json,
                   result_json, error_json, created_at, updated_at)
                   VALUES(?, ?, 'queued', ?, ?, NULL, NULL, ?, ?)""",
                (job_id, kind, idempotency_key, canonical_json(request), now, now),
            )
            return _job_dict(con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def update_job(
        self,
        job_id: str,
        status: str,
        *,
        result: dict[str, Any] | None = None,
        failure: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if status not in {"queued", "running", "completed", "failed", "cancelled"}:
            raise error("invalid_job_status", "Unknown job status.")
        with self.transaction() as con:
            row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise error("job_not_found", "Job was not found.", job_id=job_id)
            if row["status"] in {"completed", "failed", "cancelled"} and row["status"] != status:
                raise error("job_terminal", "Completed, failed, or cancelled jobs cannot transition.")
            con.execute(
                "UPDATE jobs SET status=?, result_json=?, error_json=?, updated_at=? WHERE id=?",
                (
                    status,
                    canonical_json(result) if result is not None else row["result_json"],
                    canonical_json(failure) if failure is not None else row["error_json"],
                    utc_now(),
                    job_id,
                ),
            )
            return _job_dict(con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self.reader() as con:
            row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise error("job_not_found", "Job was not found.", job_id=job_id)
            return _job_dict(row)

    def list_jobs(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.reader() as con:
            rows = con.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC, id LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
            total = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        return {"items": [_job_dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}


def _job_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    for name in ("request_json", "result_json", "error_json"):
        target = name.removesuffix("_json")
        raw = data.pop(name)
        data[target] = json.loads(raw) if raw else None
    return data
