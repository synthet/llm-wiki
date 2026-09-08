"""Application services shared without divergence by CLI and MCP adapters."""

from __future__ import annotations

import base64
import json
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any

import yaml

from .config import WikiConfig
from .domain import (
    AGENT_REQUEST_VERSION,
    EXPORT_VERSION,
    PARSER_VERSION,
    canonical_json,
    digest_bytes,
    digest_text,
    utc_now,
    validate_locator,
    validate_transition,
)
from .errors import LLMWikiError, error
from .ingest import (
    acquire_file,
    acquire_url,
    extract,
    extraction_config_digest,
    rebuild_node_ids,
)
from .providers import OpenAICompatibleProvider, ProviderConfig
from .render import render_pages, slugify
from .store import EXPORT_TABLES, Store
from .tree import persist_nodes

WORD_RE = re.compile(r"\w+", re.UNICODE)


class WikiService:
    def __init__(self, root: Path, provider: ProviderConfig | None = None):
        self.config = WikiConfig.load(Path(root))
        self.store = Store(self.config.db_path)
        self.provider = provider or ProviderConfig()
        self.provider.validate()

    @classmethod
    def init(cls, root: Path, *, force: bool = False) -> dict[str, Any]:
        root = Path(root).resolve()
        data_dir = root / ".llmwiki"
        config_path = data_dir / "config.yaml"
        if config_path.exists() and not force:
            raise error("already_initialized", "Wiki is already initialized.", root=str(root))
        data_dir.mkdir(parents=True, exist_ok=True)
        (root / "wiki" / "pages").mkdir(parents=True, exist_ok=True)
        (root / "wiki" / "notes").mkdir(parents=True, exist_ok=True)
        config = {
            "version": 1,
            "allowed_roots": ["."],
            "limits": {
                "max_bytes": 25 * 1024 * 1024,
                "max_download_bytes": 25 * 1024 * 1024,
                "max_pdf_pages": 500,
                "parse_timeout_seconds": 30,
                "http_timeout_seconds": 20,
            },
        }
        config_path.write_text(yaml.safe_dump(config, sort_keys=True, allow_unicode=True), encoding="utf-8")
        service = cls(root)
        service.store.initialize()
        return {"root": str(root), "database": str(service.config.db_path), "created": True}

    def ingest_file(
        self,
        path: Path,
        *,
        source_id: str | None = None,
        rights: str = "unknown",
    ) -> dict[str, Any]:
        data, uri, name = acquire_file(Path(path), self.config)
        return self._ingest(data, uri, name, None, source_id=source_id, rights=rights)

    def ingest_url(
        self,
        url: str,
        *,
        source_id: str | None = None,
        rights: str = "unknown",
    ) -> dict[str, Any]:
        data, uri, name, media_type = acquire_url(url, self.config, mode=self.provider.mode)
        return self._ingest(data, uri, name, media_type, source_id=source_id, rights=rights)

    def _ingest(
        self,
        data: bytes,
        uri: str,
        name: str,
        declared_media_type: str | None,
        *,
        source_id: str | None,
        rights: str,
    ) -> dict[str, Any]:
        if not rights.strip():
            rights = "unknown"
        extraction = extract(data, name, self.config, declared_media_type)
        config_digest = extraction_config_digest(self.config)
        source_key = source_id or uri
        with self.store.transaction() as con:
            source = con.execute("SELECT * FROM sources WHERE source_key=?", (source_key,)).fetchone()
            if source is None:
                logical_id = str(uuid.uuid4())
                con.execute(
                    """INSERT INTO sources(id, source_key, display_name, original_uri, media_type,
                       rights, created_at, current_revision_id) VALUES(?, ?, ?, ?, ?, ?, ?, NULL)""",
                    (logical_id, source_key, name, uri, extraction.media_type, rights, utc_now()),
                )
                previous_revision_id = None
            else:
                logical_id = source["id"]
                previous_revision_id = source["current_revision_id"]
                if rights != "unknown" and source["rights"] == "unknown":
                    con.execute("UPDATE sources SET rights=? WHERE id=?", (rights, logical_id))
            duplicate = con.execute(
                "SELECT * FROM source_revisions WHERE source_id=? AND digest=?",
                (logical_id, extraction.digest),
            ).fetchone()
            if duplicate:
                if previous_revision_id != duplicate["id"]:
                    con.execute(
                        "UPDATE sources SET current_revision_id=?, media_type=?, original_uri=? WHERE id=?",
                        (duplicate["id"], extraction.media_type, uri, logical_id),
                    )
                    self._mark_revision_dependents_stale(con, previous_revision_id)
                    self.store.bump_state(con)
                return {
                    "source_id": logical_id,
                    "revision_id": duplicate["id"],
                    "digest": extraction.digest,
                    "status": duplicate["status"],
                    "reused": True,
                    "parsed": False,
                }
            revision_id = str(uuid.uuid4())
            object_path = self._store_object(extraction.digest, data)
            con.execute(
                """INSERT INTO source_revisions(
                   id, source_id, digest, content_path, byte_size, acquired_at, parser_version,
                   config_digest, extracted_text, extraction_json, status)
                   VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    revision_id,
                    logical_id,
                    extraction.digest,
                    str(object_path.relative_to(self.config.data_dir).as_posix()),
                    len(data),
                    utc_now(),
                    PARSER_VERSION,
                    config_digest,
                    extraction.text,
                    canonical_json(extraction.metadata),
                    extraction.status,
                ),
            )
            nodes = rebuild_node_ids(extraction, revision_id)
            persist_nodes(con, revision_id, nodes)
            con.execute(
                "UPDATE sources SET current_revision_id=?, media_type=?, original_uri=? WHERE id=?",
                (revision_id, extraction.media_type, uri, logical_id),
            )
            if previous_revision_id and previous_revision_id != revision_id:
                self._mark_revision_dependents_stale(con, previous_revision_id)
            self.store.bump_state(con)
        return {
            "source_id": logical_id,
            "revision_id": revision_id,
            "digest": extraction.digest,
            "status": extraction.status,
            "reused": False,
            "parsed": True,
            "nodes": len(nodes),
        }

    def _store_object(self, digest: str, data: bytes) -> Path:
        path = self.config.objects_dir / digest[:2] / digest
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = path.read_bytes()
            if digest_bytes(existing) != digest:
                raise error("object_digest_mismatch", "Existing object does not match its digest.")
            return path
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(data)
        if digest_bytes(temporary.read_bytes()) != digest:
            temporary.unlink(missing_ok=True)
            raise error("object_write_failed", "Stored object failed digest verification.")
        temporary.replace(path)
        return path

    @staticmethod
    def _mark_revision_dependents_stale(con: sqlite3.Connection, revision_id: str | None) -> int:
        if not revision_id:
            return 0
        rows = con.execute(
            """SELECT cr.id, cr.status FROM claim_revisions cr
               JOIN dependencies d ON d.claim_revision_id=cr.id
               WHERE d.source_revision_id=? AND cr.is_current=1
               AND cr.status IN ('candidate','reviewed','disputed')""",
            (revision_id,),
        ).fetchall()
        for row in rows:
            validate_transition(row["status"], "stale")
            con.execute("UPDATE claim_revisions SET status='stale' WHERE id=?", (row["id"],))
        return len(rows)

    def list_sources(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        _pagination(limit, offset)
        with self.store.reader() as con:
            rows = con.execute(
                """SELECT s.*, r.digest AS current_digest, r.status AS current_status
                   FROM sources s LEFT JOIN source_revisions r ON r.id=s.current_revision_id
                   ORDER BY s.created_at, s.id LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
            total = con.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}

    def get_source(self, source_id: str) -> dict[str, Any]:
        with self.store.reader() as con:
            source = con.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
            if not source:
                raise error("source_not_found", "Source was not found.", source_id=source_id)
            revisions = con.execute(
                """SELECT id, digest, byte_size, acquired_at, parser_version, config_digest, status
                   FROM source_revisions WHERE source_id=? ORDER BY acquired_at, id""",
                (source_id,),
            ).fetchall()
        result = dict(source)
        result["revisions"] = [dict(row) for row in revisions]
        return result

    def get_revision(self, revision_id: str, *, include_text: bool = True) -> dict[str, Any]:
        with self.store.reader() as con:
            row = con.execute("SELECT * FROM source_revisions WHERE id=?", (revision_id,)).fetchone()
            if not row:
                raise error("revision_not_found", "Source revision was not found.")
        result = dict(row)
        result["extraction"] = json.loads(result.pop("extraction_json"))
        if not include_text:
            result.pop("extracted_text")
        return result

    def get_claim_revision(self, claim_revision_id: str) -> dict[str, Any]:
        with self.store.reader() as con:
            row = con.execute(
                """SELECT cr.*, e.canonical_name AS entity_name FROM claim_revisions cr
                   JOIN claims c ON c.id=cr.claim_id JOIN entities e ON e.id=c.entity_id
                   WHERE cr.id=?""",
                (claim_revision_id,),
            ).fetchone()
            if not row:
                raise error("claim_revision_not_found", "Claim revision was not found.")
            result = self._claim_dict(con, row, include_evidence=True)
            result["reviews"] = [
                dict(item)
                for item in con.execute(
                    "SELECT * FROM review_events WHERE claim_revision_id=? ORDER BY created_at, id",
                    (claim_revision_id,),
                )
            ]
        return result

    def get_evidence(self, evidence_id: str) -> dict[str, Any]:
        with self.store.reader() as con:
            row = con.execute(
                """SELECT ev.*, sr.digest AS source_digest FROM evidence ev JOIN source_revisions sr
                   ON sr.id=ev.source_revision_id WHERE ev.id=?""",
                (evidence_id,),
            ).fetchone()
            if not row:
                raise error("evidence_not_found", "Evidence was not found.")
        result = dict(row)
        result["locator"] = json.loads(result.pop("locator_json"))
        return result

    def list_nodes(
        self,
        revision_id: str,
        *,
        parent_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        _pagination(limit, offset, maximum=500)
        with self.store.reader() as con:
            revision = con.execute("SELECT id FROM source_revisions WHERE id=?", (revision_id,)).fetchone()
            if not revision:
                raise error("revision_not_found", "Source revision was not found.")
            condition = "parent_id IS NULL" if parent_id is None else "parent_id=?"
            params: tuple[Any, ...] = (revision_id,) if parent_id is None else (revision_id, parent_id)
            total = con.execute(
                f"SELECT COUNT(*) FROM document_nodes WHERE source_revision_id=? AND {condition}", params
            ).fetchone()[0]
            rows = con.execute(
                f"""SELECT * FROM document_nodes WHERE source_revision_id=? AND {condition}
                    ORDER BY document_order LIMIT ? OFFSET ?""",
                (*params, limit, offset),
            ).fetchall()
        return {
            "items": [_node_dict(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def read_node(self, node_id: str) -> dict[str, Any]:
        with self.store.reader() as con:
            row = con.execute("SELECT * FROM document_nodes WHERE id=?", (node_id,)).fetchone()
            if not row:
                raise error("node_not_found", "Document-tree node was not found.")
            revision = con.execute("SELECT * FROM source_revisions WHERE id=?", (row["source_revision_id"],)).fetchone()
            locator = json.loads(row["locator_json"])
            text = self._resolve_locator(revision, locator)
        result = _node_dict(row)
        result["text"] = text
        return result

    @staticmethod
    def _resolve_locator(revision: sqlite3.Row, locator: dict[str, Any]) -> str:
        metadata = json.loads(revision["extraction_json"])
        pages = metadata.get("pages") if metadata.get("kind") == "pdf" else None
        return validate_locator(locator, revision["extracted_text"], pages)

    def compile_export(self, revision_ids: list[str] | None = None, *, mode: str = "agent") -> dict[str, Any]:
        if mode not in {"agent", "api", "local"}:
            raise error("invalid_provider_mode", "Compilation mode is invalid.")
        with self.store.transaction() as con:
            if revision_ids:
                placeholders = ",".join("?" for _ in revision_ids)
                revisions = con.execute(
                    f"""SELECT r.* FROM source_revisions r JOIN sources s ON s.current_revision_id=r.id
                       WHERE r.id IN ({placeholders}) ORDER BY r.id""",
                    revision_ids,
                ).fetchall()
                if len(revisions) != len(set(revision_ids)):
                    raise error("revision_not_current", "Compilation inputs must be current revisions.")
            else:
                revisions = con.execute(
                    """SELECT r.* FROM source_revisions r JOIN sources s ON s.current_revision_id=r.id
                       WHERE r.status='ready' ORDER BY r.id"""
                ).fetchall()
            state_version = self.store.state_version(con)
            run_id = str(uuid.uuid4())
            nodes: list[dict[str, Any]] = []
            remaining_chars = 500_000
            for revision in revisions:
                for node in con.execute(
                    """SELECT * FROM document_nodes WHERE source_revision_id=?
                       AND NOT EXISTS(SELECT 1 FROM document_nodes child WHERE child.parent_id=document_nodes.id)
                       ORDER BY document_order""",
                    (revision["id"],),
                ):
                    locator = json.loads(node["locator_json"])
                    content = self._resolve_locator(revision, locator)
                    if len(content) > remaining_chars:
                        break
                    remaining_chars -= len(content)
                    nodes.append(
                        {
                            "node_id": node["id"],
                            "source_revision_id": revision["id"],
                            "source_digest": revision["digest"],
                            "heading": node["heading"],
                            "locator": locator,
                            "text": content,
                        }
                    )
            request = {
                "version": AGENT_REQUEST_VERSION,
                "run_id": run_id,
                "state_version": state_version,
                "mode": mode,
                "source_revisions": [
                    {"id": row["id"], "digest": row["digest"], "source_id": row["source_id"]} for row in revisions
                ],
                "evidence_bundle": nodes,
                "limits": {"max_claims": 500, "max_claim_chars": 4000},
                "expected_response_schema": {
                    "version": 1,
                    "run_id": "uuid",
                    "state_version": "integer",
                    "claims": [
                        {
                            "entity": {"id": "optional uuid", "name": "string"},
                            "text": "atomic factual claim",
                            "supersedes_claim_revision_id": "optional uuid",
                            "evidence": [{"source_revision_id": "uuid", "locator": {}, "quote": "exact text"}],
                            "contradicts_claim_revision_ids": ["uuid"],
                        }
                    ],
                },
            }
            con.execute(
                """INSERT INTO compilation_runs(id, mode, status, state_version, provider, model,
                   prompt_digest, config_digest, input_revisions_json, request_json, result_json,
                   usage_json, created_at, completed_at)
                   VALUES(?, ?, 'exported', ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, NULL)""",
                (
                    run_id,
                    mode,
                    state_version,
                    "openai-compatible" if mode != "agent" else None,
                    self.provider.compiler_model if mode != "agent" else None,
                    digest_text(canonical_json(request["expected_response_schema"])),
                    extraction_config_digest(self.config),
                    canonical_json(request["source_revisions"]),
                    canonical_json(request),
                    utc_now(),
                ),
            )
        return request

    def compile(self, revision_ids: list[str] | None = None) -> dict[str, Any]:
        request = self.compile_export(revision_ids, mode=self.provider.mode)
        if self.provider.mode == "agent":
            return {"status": "awaiting_agent_result", "request": request}
        provider = OpenAICompatibleProvider(self.provider)
        with self.store.transaction() as con:
            con.execute("UPDATE compilation_runs SET status='running' WHERE id=?", (request["run_id"],))
        try:
            result, usage = provider.compile(request)
        except LLMWikiError as exc:
            with self.store.transaction() as con:
                con.execute(
                    "UPDATE compilation_runs SET status='failed', result_json=?, completed_at=? WHERE id=?",
                    (canonical_json({"error": exc.as_dict()}), utc_now(), request["run_id"]),
                )
            raise
        applied = self.compile_apply(result, usage=usage)
        return {"status": "completed", "result": applied}

    def compile_apply(self, result: dict[str, Any], *, usage: dict[str, Any] | None = None) -> dict[str, Any]:
        _validate_agent_result_shape(result)
        with self.store.transaction() as con:
            run = con.execute("SELECT * FROM compilation_runs WHERE id=?", (result["run_id"],)).fetchone()
            if not run:
                raise error("compilation_run_not_found", "Compilation run was not found.")
            if run["status"] not in {"exported", "running"}:
                raise error("compilation_run_closed", "Compilation run is no longer accepting results.")
            current_state = self.store.state_version(con)
            if result["state_version"] != run["state_version"] or current_state != run["state_version"]:
                raise error("stale_compilation_result", "Canonical state changed after request export.")
            inputs = {item["id"]: item["digest"] for item in json.loads(run["input_revisions_json"])}
            for revision_id, digest in inputs.items():
                row = con.execute(
                    """SELECT r.digest FROM source_revisions r JOIN sources s ON s.current_revision_id=r.id
                       WHERE r.id=?""",
                    (revision_id,),
                ).fetchone()
                if not row or row["digest"] != digest:
                    raise error("stale_compilation_result", "A compilation source revision changed.")
            created: list[str] = []
            reused: list[str] = []
            for proposal in result["claims"]:
                entity_id = self._resolve_or_create_entity(con, proposal["entity"])
                text = proposal["text"].strip()
                if not text or len(text) > 4000:
                    raise error("invalid_claim", "Claim text must contain 1–4000 characters.")
                # Validate every evidence item before duplicate/no-op detection.  This
                # keeps invalid proposals from being silently accepted merely because
                # an identical current claim already exists.
                validated_evidence: list[tuple[str, dict[str, Any], str]] = []
                for evidence in proposal["evidence"]:
                    revision_id = evidence["source_revision_id"]
                    if revision_id not in inputs:
                        raise error("invalid_evidence_revision", "Evidence revision was not in the request.")
                    revision = con.execute("SELECT * FROM source_revisions WHERE id=?", (revision_id,)).fetchone()
                    exact = self._resolve_locator(revision, evidence["locator"])
                    if evidence["quote"] != exact:
                        raise error("evidence_quote_mismatch", "Evidence quote does not match locator text.")
                    validated_evidence.append((revision_id, evidence["locator"], exact))
                proposed_revisions = {item["source_revision_id"] for item in proposal["evidence"]}
                duplicate = con.execute(
                    """SELECT cr.id FROM claim_revisions cr JOIN claims c ON c.id=cr.claim_id
                       WHERE c.entity_id=? AND cr.content_digest=? AND cr.is_current=1""",
                    (entity_id, digest_text(text)),
                ).fetchone()
                if duplicate:
                    dependencies = {
                        row[0]
                        for row in con.execute(
                            "SELECT source_revision_id FROM dependencies WHERE claim_revision_id=?",
                            (duplicate["id"],),
                        )
                    }
                    if dependencies == proposed_revisions:
                        reused.append(duplicate["id"])
                        continue
                supersedes = proposal.get("supersedes_claim_revision_id")
                claim_revision_id = str(uuid.uuid4())
                if supersedes:
                    prior = con.execute(
                        """SELECT cr.*, c.entity_id FROM claim_revisions cr JOIN claims c
                           ON c.id=cr.claim_id WHERE cr.id=? AND cr.is_current=1""",
                        (supersedes,),
                    ).fetchone()
                    if not prior or prior["entity_id"] != entity_id:
                        raise error("invalid_supersession", "Superseded claim revision is not a current entity claim.")
                    validate_transition(prior["status"], "superseded")
                    claim_id = prior["claim_id"]
                    con.execute(
                        "UPDATE claim_revisions SET status='superseded', is_current=0 WHERE id=?",
                        (supersedes,),
                    )
                else:
                    claim_id = str(uuid.uuid4())
                    con.execute(
                        "INSERT INTO claims(id, entity_id, created_at) VALUES(?, ?, ?)",
                        (claim_id, entity_id, utc_now()),
                    )
                con.execute(
                    """INSERT INTO claim_revisions(id, claim_id, text, status, created_at,
                       supersedes_revision_id, content_digest, is_current)
                       VALUES(?, ?, ?, 'candidate', ?, ?, ?, 1)""",
                    (claim_revision_id, claim_id, text, utc_now(), supersedes, digest_text(text)),
                )
                for revision_id, locator, exact in validated_evidence:
                    con.execute(
                        """INSERT INTO evidence(id, claim_revision_id, source_revision_id,
                           locator_json, quote, created_at) VALUES(?, ?, ?, ?, ?, ?)""",
                        (
                            str(uuid.uuid4()),
                            claim_revision_id,
                            revision_id,
                            canonical_json(locator),
                            exact,
                            utc_now(),
                        ),
                    )
                    con.execute(
                        "INSERT OR IGNORE INTO dependencies(claim_revision_id, source_revision_id) VALUES(?, ?)",
                        (claim_revision_id, revision_id),
                    )
                for left_id in proposal.get("contradicts_claim_revision_ids", []):
                    if not con.execute("SELECT 1 FROM claim_revisions WHERE id=?", (left_id,)).fetchone():
                        raise error("contradiction_target_missing", "Contradiction target was not found.")
                    pair = sorted((left_id, claim_revision_id))
                    con.execute(
                        """INSERT OR IGNORE INTO contradictions(id, left_claim_revision_id,
                           right_claim_revision_id, status, reason, created_at)
                           VALUES(?, ?, ?, 'open', ?, ?)""",
                        (str(uuid.uuid4()), pair[0], pair[1], "model-proposed disagreement", utc_now()),
                    )
                    con.execute(
                        "UPDATE claim_revisions SET status='disputed' WHERE id=? AND status='candidate'",
                        (claim_revision_id,),
                    )
                created.append(claim_revision_id)
            if created:
                self.store.bump_state(con)
            con.execute(
                """UPDATE compilation_runs SET status='completed', result_json=?, usage_json=?,
                   completed_at=? WHERE id=?""",
                (
                    canonical_json(result),
                    canonical_json(usage) if usage is not None else None,
                    utc_now(),
                    run["id"],
                ),
            )
        return {
            "run_id": result["run_id"],
            "claim_revision_ids": created,
            "reused_claim_revision_ids": reused,
            "count": len(created),
        }

    def _resolve_or_create_entity(self, con: sqlite3.Connection, value: dict[str, Any]) -> str:
        entity_id = value.get("id")
        name = value.get("name")
        if not isinstance(name, str) or not name.strip():
            raise error("invalid_entity", "Entity name is required.")
        if entity_id:
            row = con.execute("SELECT * FROM entities WHERE id=?", (entity_id,)).fetchone()
            if not row or row["canonical_name"] != name.strip():
                raise error("entity_identity_mismatch", "Entity identity does not match canonical state.")
            return entity_id
        normalized = _normalize_alias(name)
        matches = con.execute(
            "SELECT entity_id FROM entity_aliases WHERE normalized_alias=? ORDER BY entity_id",
            (normalized,),
        ).fetchall()
        if len(matches) > 1:
            raise error("ambiguous_entity", "Entity alias resolves to multiple identities.", name=name)
        if matches:
            return matches[0]["entity_id"]
        entity_id = str(uuid.uuid4())
        base_slug = slugify(name)
        slug = base_slug
        if con.execute("SELECT 1 FROM entities WHERE slug=?", (slug,)).fetchone():
            slug = f"{base_slug}-{entity_id[:8]}"
        con.execute(
            "INSERT INTO entities(id, canonical_name, slug, created_at) VALUES(?, ?, ?, ?)",
            (entity_id, name.strip(), slug, utc_now()),
        )
        con.execute(
            "INSERT INTO entity_aliases(entity_id, alias, normalized_alias) VALUES(?, ?, ?)",
            (entity_id, name.strip(), normalized),
        )
        return entity_id

    def review_list(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        _pagination(limit, offset)
        with self.store.reader() as con:
            total = con.execute(
                "SELECT COUNT(*) FROM claim_revisions WHERE is_current=1 AND status IN ('candidate','disputed')"
            ).fetchone()[0]
            rows = con.execute(
                """SELECT cr.*, e.canonical_name AS entity_name
                   FROM claim_revisions cr JOIN claims c ON c.id=cr.claim_id
                   JOIN entities e ON e.id=c.entity_id
                   WHERE cr.is_current=1 AND cr.status IN ('candidate','disputed')
                   ORDER BY cr.created_at, cr.id LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
            items = [self._claim_dict(con, row, include_evidence=True) for row in rows]
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def review(
        self,
        claim_revision_id: str,
        action: str,
        *,
        reviewer: str,
        note: str,
    ) -> dict[str, Any]:
        if not reviewer.strip() or not note.strip():
            raise error("review_attribution_required", "Reviewer identity and review note are required.")
        target = {"approve": "reviewed", "reject": "retracted", "retract": "retracted"}.get(action)
        if target is None:
            raise error("invalid_review_action", "Review action must be approve, reject, or retract.")
        with self.store.transaction() as con:
            row = con.execute("SELECT * FROM claim_revisions WHERE id=?", (claim_revision_id,)).fetchone()
            if not row:
                raise error("claim_revision_not_found", "Claim revision was not found.")
            if action == "retract" and row["status"] not in {"reviewed", "disputed"}:
                raise error("invalid_state_transition", "Only reviewed or disputed claims can be retracted.")
            if action == "reject" and row["status"] not in {"candidate", "disputed"}:
                raise error("invalid_state_transition", "Only candidate or disputed claims can be rejected.")
            validate_transition(row["status"], target)
            evidence = con.execute(
                """SELECT ev.*, sr.* FROM evidence ev JOIN source_revisions sr
                   ON sr.id=ev.source_revision_id WHERE ev.claim_revision_id=? ORDER BY ev.id""",
                (claim_revision_id,),
            ).fetchall()
            if target == "reviewed" and not evidence:
                raise error("review_evidence_required", "Reviewed claims require immutable evidence.")
            for item in evidence:
                actual = self._resolve_locator(item, json.loads(item["locator_json"]))
                if actual != item["quote"]:
                    raise error("evidence_quote_mismatch", "Claim evidence no longer resolves exactly.")
                object_path = self.config.data_dir / item["content_path"]
                if not object_path.is_file() or digest_bytes(object_path.read_bytes()) != item["digest"]:
                    raise error("source_digest_mismatch", "Evidence source bytes failed digest verification.")
            con.execute("UPDATE claim_revisions SET status=? WHERE id=?", (target, claim_revision_id))
            event_id = str(uuid.uuid4())
            con.execute(
                """INSERT INTO review_events(id, claim_revision_id, action, reviewer, note,
                   before_status, after_status, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_id,
                    claim_revision_id,
                    action,
                    reviewer.strip(),
                    note.strip(),
                    row["status"],
                    target,
                    utc_now(),
                ),
            )
            self.store.bump_state(con)
        return {
            "review_event_id": event_id,
            "claim_revision_id": claim_revision_id,
            "before": row["status"],
            "after": target,
        }

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        statuses: list[str] | None = None,
        include_nodes: bool = False,
    ) -> dict[str, Any]:
        if not query.strip():
            raise error("empty_query", "Search query must not be empty.")
        _pagination(limit, 0, maximum=100)
        statuses = statuses or ["reviewed"]
        allowed = {"candidate", "reviewed", "disputed", "stale", "superseded", "retracted"}
        if not statuses or any(item not in allowed for item in statuses):
            raise error("invalid_status_filter", "Search contains an unknown claim status.")
        with self.store.transaction() as con:
            backend = self._ensure_index(con)
            if backend == "sqlite-fts5":
                results = self._search_fts(con, query, statuses, limit)
            else:
                results = self._search_python(con, query, statuses, limit)
            selected_nodes: list[dict[str, Any]] = []
            if include_nodes:
                selected_nodes = self._search_nodes(con, query, limit=min(limit * 2, 50), backend=backend)
            trace_id = str(uuid.uuid4())
            con.execute(
                """INSERT INTO retrieval_traces(id, query, method, backend, selected_nodes_json,
                   decision_summary, result_json, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trace_id,
                    query,
                    "lexical-hierarchical" if include_nodes else "lexical",
                    backend,
                    canonical_json([item["id"] for item in selected_nodes]),
                    "Selected by deterministic lexical score; no hidden reasoning recorded.",
                    canonical_json(results),
                    utc_now(),
                ),
            )
        return {
            "query": query,
            "backend": backend,
            "results": results,
            "nodes": selected_nodes,
            "trace_id": trace_id,
            "insufficient": not bool(results or selected_nodes),
        }

    def ask(
        self,
        question: str,
        *,
        limit: int = 8,
        statuses: list[str] | None = None,
    ) -> dict[str, Any]:
        search = self.search(question, limit=limit, statuses=statuses, include_nodes=True)
        if not search["results"]:
            return {
                "question": question,
                "answer": None,
                "citations": [],
                "insufficient": True,
                "reason": "No matching claims in the requested review states.",
                "trace_id": search["trace_id"],
                "backend": search["backend"],
            }
        statements: list[str] = []
        citations: list[dict[str, Any]] = []
        for index, claim in enumerate(search["results"], 1):
            statements.append(f"{claim['text']} [{index}]")
            citations.append(
                {
                    "number": index,
                    "claim_revision_id": claim["id"],
                    "status": claim["status"],
                    "evidence": claim["evidence"],
                }
            )
        return {
            "question": question,
            "answer": " ".join(statements),
            "citations": citations,
            "insufficient": False,
            "trace_id": search["trace_id"],
            "backend": search["backend"],
        }

    def rebuild_index(self) -> dict[str, Any]:
        with self.store.transaction() as con:
            backend = self._rebuild_index(con)
            claim_count = con.execute("SELECT COUNT(*) FROM claim_revisions WHERE is_current=1").fetchone()[0]
            node_count = con.execute("SELECT COUNT(*) FROM document_nodes").fetchone()[0]
        return {"backend": backend, "claims_indexed": claim_count, "nodes_indexed": node_count}

    @staticmethod
    def _ensure_index(con: sqlite3.Connection) -> str:
        return WikiService._rebuild_index(con)

    @staticmethod
    def _rebuild_index(con: sqlite3.Connection) -> str:
        try:
            con.execute("DROP TABLE IF EXISTS claim_fts")
            con.execute("DROP TABLE IF EXISTS node_fts")
            con.execute(
                "CREATE VIRTUAL TABLE claim_fts USING fts5("
                "id UNINDEXED, text, entity_name, tokenize='porter unicode61')"
            )
            con.execute(
                "CREATE VIRTUAL TABLE node_fts USING fts5(id UNINDEXED, heading, content, tokenize='porter unicode61')"
            )
            con.execute(
                """INSERT INTO claim_fts(id, text, entity_name)
                   SELECT cr.id, cr.text, e.canonical_name FROM claim_revisions cr
                   JOIN claims c ON c.id=cr.claim_id JOIN entities e ON e.id=c.entity_id
                   WHERE cr.is_current=1"""
            )
            nodes = con.execute(
                """SELECT n.*, r.* FROM document_nodes n JOIN source_revisions r
                   ON r.id=n.source_revision_id ORDER BY n.id"""
            ).fetchall()
            for node in nodes:
                try:
                    content = WikiService._resolve_locator(node, json.loads(node["locator_json"]))
                except LLMWikiError:
                    continue
                con.execute(
                    "INSERT INTO node_fts(id, heading, content) VALUES(?, ?, ?)",
                    (node["id"], node["heading"], content),
                )
            return "sqlite-fts5"
        except sqlite3.OperationalError:
            con.execute("DROP TABLE IF EXISTS claim_fts")
            con.execute("DROP TABLE IF EXISTS node_fts")
            return "python-lexical"

    def _search_fts(
        self,
        con: sqlite3.Connection,
        query: str,
        statuses: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        tokens = WORD_RE.findall(query.casefold())
        if not tokens:
            return []
        match = " OR ".join(f'"{token}"*' for token in tokens)
        placeholders = ",".join("?" for _ in statuses)
        rows = con.execute(
            f"""SELECT cr.*, e.canonical_name AS entity_name, bm25(claim_fts) AS rank
               FROM claim_fts JOIN claim_revisions cr ON cr.id=claim_fts.id
               JOIN claims c ON c.id=cr.claim_id JOIN entities e ON e.id=c.entity_id
               WHERE claim_fts MATCH ? AND cr.is_current=1 AND cr.status IN ({placeholders})
               ORDER BY rank, cr.id LIMIT ?""",
            (match, *statuses, limit),
        ).fetchall()
        results = [self._claim_dict(con, row, include_evidence=True) for row in rows]
        for item, row in zip(results, rows, strict=True):
            item["score"] = round(-float(row["rank"]), 6)
        return results

    def _search_python(
        self,
        con: sqlite3.Connection,
        query: str,
        statuses: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        tokens = set(WORD_RE.findall(query.casefold()))
        placeholders = ",".join("?" for _ in statuses)
        rows = con.execute(
            f"""SELECT cr.*, e.canonical_name AS entity_name
               FROM claim_revisions cr JOIN claims c ON c.id=cr.claim_id
               JOIN entities e ON e.id=c.entity_id
               WHERE cr.is_current=1 AND cr.status IN ({placeholders}) ORDER BY cr.id""",
            statuses,
        ).fetchall()
        scored: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            words = WORD_RE.findall((row["text"] + " " + row["entity_name"]).casefold())
            score = sum(words.count(token) for token in tokens)
            if score:
                scored.append((float(score), row))
        scored.sort(key=lambda item: (-item[0], item[1]["id"]))
        results = [self._claim_dict(con, row, include_evidence=True) for _, row in scored[:limit]]
        for result, (score, _) in zip(results, scored[:limit], strict=True):
            result["score"] = score
        return results

    def _search_nodes(self, con: sqlite3.Connection, query: str, *, limit: int, backend: str) -> list[dict[str, Any]]:
        if backend == "sqlite-fts5":
            tokens = WORD_RE.findall(query.casefold())
            if not tokens:
                return []
            match = " OR ".join(f'"{token}"*' for token in tokens)
            rows = con.execute(
                """SELECT n.*, bm25(node_fts) AS rank FROM node_fts
                   JOIN document_nodes n ON n.id=node_fts.id WHERE node_fts MATCH ?
                   ORDER BY rank, n.document_order LIMIT ?""",
                (match, limit),
            ).fetchall()
            items = [_node_dict(row) for row in rows]
            for item, row in zip(items, rows, strict=True):
                item["score"] = round(-float(row["rank"]), 6)
            return items
        tokens = set(WORD_RE.findall(query.casefold()))
        candidates: list[tuple[int, sqlite3.Row]] = []
        for row in con.execute("SELECT * FROM document_nodes ORDER BY source_revision_id, document_order"):
            score = sum(row["heading"].casefold().count(token) for token in tokens)
            if score:
                candidates.append((score, row))
        candidates.sort(key=lambda item: (-item[0], item[1]["id"]))
        items = [_node_dict(row) for _, row in candidates[:limit]]
        for item, (score, _) in zip(items, candidates[:limit], strict=True):
            item["score"] = float(score)
        return items

    @staticmethod
    def _claim_dict(con: sqlite3.Connection, row: sqlite3.Row, *, include_evidence: bool) -> dict[str, Any]:
        result = {
            "id": row["id"],
            "claim_id": row["claim_id"],
            "entity_name": dict(row).get("entity_name"),
            "text": row["text"],
            "status": row["status"],
            "created_at": row["created_at"],
            "content_digest": row["content_digest"],
        }
        if include_evidence:
            evidence = con.execute(
                """SELECT ev.*, sr.digest AS source_digest FROM evidence ev
                   JOIN source_revisions sr ON sr.id=ev.source_revision_id
                   WHERE ev.claim_revision_id=? ORDER BY ev.id""",
                (row["id"],),
            ).fetchall()
            result["evidence"] = [
                {
                    "id": item["id"],
                    "source_revision_id": item["source_revision_id"],
                    "source_digest": item["source_digest"],
                    "locator": json.loads(item["locator_json"]),
                    "quote": item["quote"],
                }
                for item in evidence
            ]
        return result

    def render(self, *, include_unreviewed: bool = False) -> dict[str, Any]:
        with self.store.transaction() as con:
            result = render_pages(con, self.config.pages_dir, include_unreviewed=include_unreviewed)
        return result

    def list_pages(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        _pagination(limit, offset)
        params: list[Any] = []
        condition = ""
        if status:
            condition = (
                "WHERE EXISTS(SELECT 1 FROM claims c JOIN claim_revisions cr "
                "ON cr.claim_id=c.id WHERE c.entity_id=e.id AND cr.is_current=1 AND cr.status=?)"
            )
            params.append(status)
        with self.store.reader() as con:
            total = con.execute(f"SELECT COUNT(*) FROM entities e {condition}", params).fetchone()[0]
            rows = con.execute(
                f"""SELECT e.*, (SELECT COUNT(*) FROM claims c JOIN claim_revisions cr
                    ON cr.claim_id=c.id WHERE c.entity_id=e.id AND cr.is_current=1) AS claim_count
                    FROM entities e {condition} ORDER BY e.slug, e.id LIMIT ? OFFSET ?""",
                (*params, limit, offset),
            ).fetchall()
        return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}

    def new_entity(self, title: str, aliases: list[str] | None = None) -> dict[str, Any]:
        if not title.strip():
            raise error("invalid_entity", "Entity title must not be empty.")
        with self.store.transaction() as con:
            entity_id = self._resolve_or_create_entity(con, {"name": title})
            for alias in aliases or []:
                if alias.strip():
                    con.execute(
                        "INSERT OR IGNORE INTO entity_aliases(entity_id, alias, normalized_alias) VALUES(?, ?, ?)",
                        (entity_id, alias.strip(), _normalize_alias(alias)),
                    )
            self.store.bump_state(con)
            row = con.execute("SELECT * FROM entities WHERE id=?", (entity_id,)).fetchone()
        return dict(row)

    def get_page(self, ref: str) -> dict[str, Any]:
        normalized = _normalize_alias(ref)
        with self.store.reader() as con:
            rows = con.execute(
                """SELECT e.* FROM entities e LEFT JOIN entity_aliases a ON a.entity_id=e.id
                   WHERE e.id=? OR e.slug=? OR a.normalized_alias=? GROUP BY e.id ORDER BY e.id""",
                (ref, ref, normalized),
            ).fetchall()
            if not rows:
                raise error("page_not_found", "Entity/page was not found.", ref=ref)
            if len(rows) > 1:
                raise error("ambiguous_entity", "Page reference resolves to multiple entities.", ref=ref)
            entity = dict(rows[0])
            claims = con.execute(
                """SELECT cr.*, e.canonical_name AS entity_name FROM claim_revisions cr
                   JOIN claims c ON c.id=cr.claim_id JOIN entities e ON e.id=c.entity_id
                   WHERE c.entity_id=? AND cr.is_current=1 ORDER BY cr.created_at, cr.id""",
                (entity["id"],),
            ).fetchall()
            entity["claims"] = [self._claim_dict(con, row, include_evidence=True) for row in claims]
            entity["aliases"] = [
                row[0]
                for row in con.execute(
                    "SELECT alias FROM entity_aliases WHERE entity_id=? ORDER BY normalized_alias",
                    (entity["id"],),
                )
            ]
        entity["path"] = str(self.config.pages_dir / f"{entity['slug']}.md")
        return entity

    def backlinks(self, ref: str) -> dict[str, Any]:
        page = self.get_page(ref)
        # Claim dependencies are the canonical graph; Markdown wikilinks are only projections.
        with self.store.reader() as con:
            sources = con.execute(
                """SELECT DISTINCT s.id, s.display_name, s.current_revision_id FROM sources s
                   JOIN source_revisions sr ON sr.source_id=s.id JOIN dependencies d
                   ON d.source_revision_id=sr.id JOIN claim_revisions cr ON cr.id=d.claim_revision_id
                   JOIN claims c ON c.id=cr.claim_id WHERE c.entity_id=? ORDER BY s.id""",
                (page["id"],),
            ).fetchall()
        return {"entity_id": page["id"], "dependencies": [dict(row) for row in sources]}

    def stats(self) -> dict[str, Any]:
        with self.store.reader() as con:
            counts = {
                "sources": con.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
                "source_revisions": con.execute("SELECT COUNT(*) FROM source_revisions").fetchone()[0],
                "entities": con.execute("SELECT COUNT(*) FROM entities").fetchone()[0],
                "claims": con.execute("SELECT COUNT(*) FROM claims").fetchone()[0],
                "claim_revisions": con.execute("SELECT COUNT(*) FROM claim_revisions").fetchone()[0],
                "evidence": con.execute("SELECT COUNT(*) FROM evidence").fetchone()[0],
                "contradictions": con.execute("SELECT COUNT(*) FROM contradictions").fetchone()[0],
                "document_nodes": con.execute("SELECT COUNT(*) FROM document_nodes").fetchone()[0],
                "jobs": con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
            }
            statuses = {
                row["status"]: row["count"]
                for row in con.execute(
                    "SELECT status, COUNT(*) AS count FROM claim_revisions GROUP BY status ORDER BY status"
                )
            }
            reviewed = statuses.get("reviewed", 0)
            reviewed_with_evidence = con.execute(
                """SELECT COUNT(DISTINCT cr.id) FROM claim_revisions cr JOIN evidence ev
                   ON ev.claim_revision_id=cr.id WHERE cr.status='reviewed'"""
            ).fetchone()[0]
            backend = (
                "sqlite-fts5"
                if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='claim_fts'").fetchone()
                else "not-built"
            )
        counts["by_status"] = statuses
        counts["reviewed_citation_coverage"] = reviewed_with_evidence / reviewed if reviewed else None
        counts["index_backend"] = backend
        return counts

    def validate(self) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        with self.store.reader() as con:
            revisions = con.execute("SELECT * FROM source_revisions ORDER BY id").fetchall()
            for revision in revisions:
                path = self.config.data_dir / revision["content_path"]
                if not path.is_file():
                    issues.append(_issue("missing_source_bytes", revision_id=revision["id"]))
                elif digest_bytes(path.read_bytes()) != revision["digest"]:
                    issues.append(_issue("source_digest_mismatch", revision_id=revision["id"]))
            for evidence in con.execute(
                """SELECT ev.*, sr.* FROM evidence ev JOIN source_revisions sr
                   ON sr.id=ev.source_revision_id ORDER BY ev.id"""
            ):
                try:
                    exact = self._resolve_locator(evidence, json.loads(evidence["locator_json"]))
                    if exact != evidence["quote"]:
                        issues.append(_issue("evidence_quote_mismatch", evidence_id=evidence["id"]))
                except (LLMWikiError, json.JSONDecodeError):
                    issues.append(_issue("invalid_locator", evidence_id=evidence["id"]))
            missing_evidence = con.execute(
                """SELECT cr.id FROM claim_revisions cr LEFT JOIN evidence ev
                   ON ev.claim_revision_id=cr.id WHERE cr.status='reviewed'
                   GROUP BY cr.id HAVING COUNT(ev.id)=0 ORDER BY cr.id"""
            ).fetchall()
            issues.extend(
                _issue("reviewed_claim_without_evidence", claim_revision_id=row["id"]) for row in missing_evidence
            )
            bad_dependencies = con.execute(
                """SELECT ev.id FROM evidence ev LEFT JOIN dependencies d
                   ON d.claim_revision_id=ev.claim_revision_id AND d.source_revision_id=ev.source_revision_id
                   WHERE d.claim_revision_id IS NULL ORDER BY ev.id"""
            ).fetchall()
            issues.extend(_issue("missing_dependency", evidence_id=row["id"]) for row in bad_dependencies)
            for state in con.execute("SELECT * FROM render_state ORDER BY page_path"):
                path = Path(state["page_path"])
                if not path.is_absolute():
                    path = self.config.root / path
                if not path.exists():
                    issues.append(_issue("rendered_page_missing", path=str(path)))
                elif digest_bytes(path.read_bytes()) != state["file_digest"]:
                    issues.append(_issue("render_conflict", path=str(path)))
            contradictions = con.execute(
                """SELECT co.id FROM contradictions co LEFT JOIN claim_revisions l
                   ON l.id=co.left_claim_revision_id LEFT JOIN claim_revisions r
                   ON r.id=co.right_claim_revision_id WHERE l.id IS NULL OR r.id IS NULL"""
            ).fetchall()
            issues.extend(_issue("invalid_contradiction", contradiction_id=row["id"]) for row in contradictions)
        return {"ok": not issues, "issues": issues, "error_count": len(issues)}

    def export_json(self, path: Path) -> dict[str, Any]:
        payload = {
            "format": "llmwiki-export",
            "version": EXPORT_VERSION,
            "created_at": utc_now(),
            "schema_version": 1,
            "tables": self.store.dump(),
            "objects": {},
        }
        digests: set[str] = set()
        for revision in payload["tables"]["source_revisions"]:
            digest = revision["digest"]
            if digest in digests:
                continue
            object_path = self.config.data_dir / revision["content_path"]
            data = object_path.read_bytes()
            if digest_bytes(data) != digest:
                raise error("source_digest_mismatch", "Cannot export corrupt source object.")
            payload["objects"][digest] = base64.b64encode(data).decode("ascii")
            digests.add(digest)
        encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(target)
        return {"path": str(target), "digest": digest_bytes(encoded), "objects": len(digests)}

    def import_json(self, path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise error("invalid_import", "Import file is unreadable or invalid JSON.") from exc
        if payload.get("format") != "llmwiki-export" or payload.get("version") != EXPORT_VERSION:
            raise error("unsupported_import_version", "Import format or version is unsupported.")
        tables = payload.get("tables")
        objects = payload.get("objects")
        if not isinstance(tables, dict) or not isinstance(objects, dict):
            raise error("invalid_import", "Import payload is missing tables or objects.")
        decoded: dict[str, bytes] = {}
        for digest, value in objects.items():
            try:
                data = base64.b64decode(value, validate=True)
            except Exception as exc:
                raise error("invalid_import", "Import contains invalid object encoding.") from exc
            if digest_bytes(data) != digest:
                raise error("invalid_import_digest", "Imported object digest does not match bytes.")
            decoded[digest] = data
        with self.store.transaction() as con:
            nonempty = sum(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in EXPORT_TABLES)
            if nonempty:
                raise error("import_target_not_empty", "JSON import requires an empty canonical store.")
            for revision in tables.get("source_revisions", []):
                data = decoded.get(revision["digest"])
                if data is None:
                    raise error("invalid_import", "Import omitted immutable source bytes.")
                self._store_object(revision["digest"], data)
            for table in EXPORT_TABLES:
                rows = tables.get(table, [])
                if not isinstance(rows, list):
                    raise error("invalid_import", f"Import table {table} must be a list.")
                if table == "document_nodes":
                    rows = sorted(rows, key=lambda item: (item.get("depth", 0), item.get("document_order", 0)))
                for row in rows:
                    if table == "render_state":
                        continue
                    if not isinstance(row, dict) or not row:
                        raise error("invalid_import", f"Import table {table} contains an invalid row.")
                    columns = list(row)
                    placeholders = ",".join("?" for _ in columns)
                    con.execute(
                        f"INSERT INTO {table}({','.join(columns)}) VALUES({placeholders})",
                        [row[column] for column in columns],
                    )
            self.store.bump_state(con)
        return {"imported": True, "tables": len(tables), "objects": len(decoded)}

    def import_markdown(self, source_dir: Path) -> dict[str, Any]:
        directory = Path(source_dir).resolve(strict=True)
        if not directory.is_dir():
            raise error("legacy_import_not_directory", "Markdown import source must be a directory.")
        paths = sorted(directory.rglob("*.md"))
        imported_entities = 0
        imported_claims = 0
        with self.store.transaction() as con:
            for path in paths:
                raw = path.read_text(encoding="utf-8")
                metadata, body = _parse_frontmatter(raw)
                title = str(metadata.get("title") or path.stem).strip()
                requested_id = str(metadata.get("id") or "")
                if requested_id:
                    try:
                        uuid.UUID(requested_id)
                    except ValueError:
                        requested_id = ""
                entity = {"name": title}
                if requested_id and not con.execute("SELECT 1 FROM entities WHERE id=?", (requested_id,)).fetchone():
                    entity_id = requested_id
                    base_slug = slugify(title)
                    slug = base_slug
                    if con.execute("SELECT 1 FROM entities WHERE slug=?", (slug,)).fetchone():
                        slug = f"{base_slug}-{entity_id[:8]}"
                    con.execute(
                        "INSERT INTO entities(id, canonical_name, slug, created_at) VALUES(?, ?, ?, ?)",
                        (entity_id, title, slug, utc_now()),
                    )
                    con.execute(
                        "INSERT INTO entity_aliases(entity_id, alias, normalized_alias) VALUES(?, ?, ?)",
                        (entity_id, title, _normalize_alias(title)),
                    )
                else:
                    entity_id = self._resolve_or_create_entity(con, entity)
                imported_entities += 1
                claims = metadata.get("claims", [])
                texts: list[str] = []
                if isinstance(claims, list):
                    for claim in claims:
                        if isinstance(claim, str):
                            texts.append(claim)
                        elif isinstance(claim, dict):
                            text = claim.get("text") or claim.get("claim") or claim.get("statement")
                            if isinstance(text, str):
                                texts.append(text)
                if not texts:
                    cleaned = _legacy_body_text(body)
                    if cleaned:
                        texts.append(cleaned[:4000])
                for text in texts:
                    self._insert_unverified_candidate(con, entity_id, text)
                    imported_claims += 1
            if paths:
                self.store.bump_state(con)
        return {
            "source_directory": str(directory),
            "files_preserved": len(paths),
            "entities_imported": imported_entities,
            "candidate_claims_imported": imported_claims,
        }

    @staticmethod
    def _insert_unverified_candidate(con: sqlite3.Connection, entity_id: str, text: str) -> str:
        text = " ".join(text.split()).strip()
        if not text:
            raise error("invalid_claim", "Legacy claim text is empty.")
        claim_id, revision_id = str(uuid.uuid4()), str(uuid.uuid4())
        con.execute(
            "INSERT INTO claims(id, entity_id, created_at) VALUES(?, ?, ?)",
            (claim_id, entity_id, utc_now()),
        )
        con.execute(
            """INSERT INTO claim_revisions(id, claim_id, text, status, created_at,
               supersedes_revision_id, content_digest, is_current)
               VALUES(?, ?, ?, 'candidate', ?, NULL, ?, 1)""",
            (revision_id, claim_id, text, utc_now(), digest_text(text)),
        )
        return revision_id

    def refresh(self, source_id: str | None = None) -> dict[str, Any]:
        with self.store.reader() as con:
            if source_id:
                rows = con.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchall()
                if not rows:
                    raise error("source_not_found", "Source was not found.")
            else:
                rows = con.execute("SELECT * FROM sources ORDER BY id").fetchall()
        results: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []
        for row in rows:
            uri = row["original_uri"]
            if uri.startswith("file:"):
                from urllib.parse import urlsplit
                from urllib.request import url2pathname

                path = Path(url2pathname(urlsplit(uri).path))
                results.append(self.ingest_file(path, source_id=row["source_key"], rights=row["rights"]))
            else:
                skipped.append({"source_id": row["id"], "reason": "URL refresh must be explicit"})
        return {"refreshed": results, "skipped": skipped}

    def review_history(self, claim_revision_id: str) -> dict[str, Any]:
        with self.store.reader() as con:
            rows = con.execute(
                "SELECT * FROM review_events WHERE claim_revision_id=? ORDER BY created_at, id",
                (claim_revision_id,),
            ).fetchall()
        return {"claim_revision_id": claim_revision_id, "events": [dict(row) for row in rows]}

    def list_contradictions(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        _pagination(limit, offset)
        with self.store.reader() as con:
            total = con.execute("SELECT COUNT(*) FROM contradictions").fetchone()[0]
            rows = con.execute(
                "SELECT * FROM contradictions ORDER BY created_at, id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}

    def get_trace(self, trace_id: str) -> dict[str, Any]:
        with self.store.reader() as con:
            row = con.execute("SELECT * FROM retrieval_traces WHERE id=?", (trace_id,)).fetchone()
            if not row:
                raise error("trace_not_found", "Retrieval trace was not found.")
        result = dict(row)
        result["selected_nodes"] = json.loads(result.pop("selected_nodes_json"))
        result["result"] = json.loads(result.pop("result_json"))
        return result

    def submit_job(
        self,
        kind: str,
        request: dict[str, Any],
        *,
        idempotency_key: str | None = None,
        wait: bool = True,
    ) -> dict[str, Any]:
        supported = {"ingest_file", "ingest_url", "compile", "render", "refresh", "import_json"}
        if kind not in supported:
            raise error("unsupported_job", "Unknown local job kind.")
        job = self.store.create_job(kind, request, idempotency_key)
        if job["status"] in {"completed", "running"} or not wait:
            return job
        self.store.update_job(job["id"], "running")
        try:
            if kind == "ingest_file":
                result = self.ingest_file(Path(request["path"]), rights=request.get("rights", "unknown"))
            elif kind == "ingest_url":
                result = self.ingest_url(request["url"], rights=request.get("rights", "unknown"))
            elif kind == "compile":
                result = self.compile(request.get("revision_ids"))
            elif kind == "render":
                result = self.render(include_unreviewed=bool(request.get("include_unreviewed")))
            elif kind == "refresh":
                result = self.refresh(request.get("source_id"))
            else:
                result = self.import_json(Path(request["path"]))
            return self.store.update_job(job["id"], "completed", result=result)
        except LLMWikiError as exc:
            self.store.update_job(job["id"], "failed", failure=exc.as_dict())
            raise

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        job = self.store.get_job(job_id)
        if job["status"] == "running":
            raise error("job_running", "Synchronous running jobs cannot be cancelled safely.")
        return self.store.update_job(job_id, "cancelled")

    def rules(self) -> dict[str, Any]:
        return {
            "canonical_store": "SQLite plus immutable content-addressed source bytes",
            "generated_claim_initial_state": "candidate",
            "default_visibility": ["reviewed"],
            "review_authority": "explicit human review event only",
            "source_instructions": "untrusted data; never executed",
            "provider_modes": ["agent", "api", "local"],
            "agent_network_calls": 0,
        }


def _normalize_alias(value: str) -> str:
    return " ".join(value.casefold().split())


def _pagination(limit: int, offset: int, maximum: int = 200) -> None:
    if not isinstance(limit, int) or not isinstance(offset, int) or not (1 <= limit <= maximum) or offset < 0:
        raise error("invalid_pagination", f"limit must be 1–{maximum} and offset must be non-negative.")


def _node_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "source_revision_id": row["source_revision_id"],
        "parent_id": row["parent_id"],
        "depth": row["depth"],
        "document_order": row["document_order"],
        "heading": row["heading"],
        "summary": row["summary"],
        "locator": json.loads(row["locator_json"]),
        "content_digest": row["content_digest"],
        "token_estimate": row["token_estimate"],
    }


def _validate_agent_result_shape(result: dict[str, Any]) -> None:
    if not isinstance(result, dict) or result.get("version") != AGENT_REQUEST_VERSION:
        raise error("invalid_compilation_result", "Compilation result version is invalid.")
    if not isinstance(result.get("run_id"), str) or not isinstance(result.get("state_version"), int):
        raise error("invalid_compilation_result", "Compilation identity fields are invalid.")
    claims = result.get("claims")
    if not isinstance(claims, list) or len(claims) > 500:
        raise error("invalid_compilation_result", "Compilation claims must be a bounded list.")
    for claim in claims:
        if not isinstance(claim, dict) or not isinstance(claim.get("entity"), dict):
            raise error("invalid_compilation_result", "Compilation claim entity is invalid.")
        if not isinstance(claim.get("text"), str) or not isinstance(claim.get("evidence"), list):
            raise error("invalid_compilation_result", "Compilation claim fields are invalid.")
        if not claim["evidence"]:
            raise error("invalid_compilation_result", "Generated claims require evidence.")
        for evidence in claim["evidence"]:
            if not isinstance(evidence, dict) or not isinstance(evidence.get("source_revision_id"), str):
                raise error("invalid_compilation_result", "Compilation evidence identity is invalid.")
            if not isinstance(evidence.get("locator"), dict) or not isinstance(evidence.get("quote"), str):
                raise error("invalid_compilation_result", "Compilation evidence fields are invalid.")
        contradictions = claim.get("contradicts_claim_revision_ids", [])
        if not isinstance(contradictions, list) or not all(isinstance(item, str) for item in contradictions):
            raise error("invalid_compilation_result", "Contradiction references are invalid.")
        supersedes = claim.get("supersedes_claim_revision_id")
        if supersedes is not None and not isinstance(supersedes, str):
            raise error("invalid_compilation_result", "Supersession reference is invalid.")


def _issue(code: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "details": details}


def _parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---\n"):
        return {}, raw
    end = raw.find("\n---", 4)
    if end < 0:
        raise error("invalid_markdown_frontmatter", "Markdown frontmatter is not terminated.")
    loaded = yaml.safe_load(raw[4:end])
    if loaded is None:
        metadata: dict[str, Any] = {}
    elif isinstance(loaded, dict):
        metadata = loaded
    else:
        raise error("invalid_markdown_frontmatter", "Markdown frontmatter must be a mapping.")
    return metadata, raw[end + 4 :].lstrip("\r\n")


def _legacy_body_text(body: str) -> str:
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    body = re.sub(r"^#{1,6}\s+.*$", "", body, flags=re.MULTILINE)
    body = re.sub(r"\[\[([^\]]+)\]\]", r"\1", body)
    return " ".join(body.split())
