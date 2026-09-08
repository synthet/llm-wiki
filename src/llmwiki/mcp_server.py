"""Maintained-SDK MCP adapter over the shared application service."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server import MCPServer

from .errors import LLMWikiError, error
from .service import WikiService


def create_server(
    root: Path,
    *,
    allow_writes: bool = False,
    allow_review: bool = False,
    max_response_bytes: int = 512_000,
) -> MCPServer:
    service = WikiService(Path(root).resolve())
    mcp = MCPServer("llmwiki")

    def result(callable_, *args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            payload = {"ok": True, "result": callable_(*args, **kwargs)}
        except LLMWikiError as exc:
            payload = {"ok": False, "error": exc.as_dict()}
        except Exception:
            payload = {
                "ok": False,
                "error": {
                    "code": "internal_error",
                    "message": "The operation failed internally.",
                    "details": {},
                    "retryable": False,
                    "next_steps": [],
                },
            }
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if len(encoded) > max_response_bytes:
            return {
                "ok": False,
                "error": error(
                    "response_too_large",
                    "Response exceeded the configured MCP size limit; use pagination or a lower limit.",
                ).as_dict(),
            }
        return payload

    def require_write() -> None:
        if not allow_writes:
            raise error("write_capability_required", "Start MCP with --allow-writes for this operation.")

    def require_review() -> None:
        if not allow_review:
            raise error("review_capability_required", "Start MCP with --allow-review for this operation.")

    @mcp.tool()
    def search(query: str, limit: int = 10, statuses: list[str] | None = None) -> dict[str, Any]:
        """Search canonical claims; defaults to current reviewed claims only."""
        return result(service.search, query, limit=limit, statuses=statuses)

    @mcp.tool()
    def ask(question: str, limit: int = 8, statuses: list[str] | None = None) -> dict[str, Any]:
        """Return a deterministic cited answer from requested claim states."""
        return result(service.ask, question, limit=limit, statuses=statuses)

    @mcp.tool()
    def list_sources(limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """List canonical sources with pagination."""
        return result(service.list_sources, limit=limit, offset=offset)

    @mcp.tool()
    def get_source(source_id: str) -> dict[str, Any]:
        """Get one source and its immutable revision history."""
        return result(service.get_source, source_id)

    @mcp.tool()
    def get_claim(claim_revision_id: str) -> dict[str, Any]:
        """Get an immutable claim revision, evidence, and review history."""
        return result(service.get_claim_revision, claim_revision_id)

    @mcp.tool()
    def get_evidence(evidence_id: str) -> dict[str, Any]:
        """Get one validated evidence record and immutable revision identity."""
        return result(service.get_evidence, evidence_id)

    @mcp.tool()
    def list_pages(limit: int = 50, offset: int = 0, status: str | None = None) -> dict[str, Any]:
        """List canonical entities/page projections."""
        return result(service.list_pages, limit=limit, offset=offset, status=status)

    @mcp.tool()
    def get_page(ref: str) -> dict[str, Any]:
        """Get an entity and its current claims by UUID, slug, or alias."""
        return result(service.get_page, ref)

    @mcp.tool()
    def search_tree(query: str, limit: int = 10) -> dict[str, Any]:
        """Search claims and local document-tree branches broad-to-narrow."""
        return result(service.search, query, limit=limit, include_nodes=True)

    @mcp.tool()
    def list_tree_nodes(
        revision_id: str, parent_id: str | None = None, limit: int = 100, offset: int = 0
    ) -> dict[str, Any]:
        """List ordered children in an immutable revision's document tree."""
        return result(
            service.list_nodes,
            revision_id,
            parent_id=parent_id,
            limit=limit,
            offset=offset,
        )

    @mcp.tool()
    def read_tree_node(node_id: str) -> dict[str, Any]:
        """Read exact source text and locator for one tree node."""
        return result(service.read_node, node_id)

    @mcp.tool()
    def validate() -> dict[str, Any]:
        """Validate digests, evidence, dependencies, and render conflicts."""
        return result(service.validate)

    @mcp.tool()
    def stats() -> dict[str, Any]:
        """Return canonical store statistics."""
        return result(service.stats)

    @mcp.tool()
    def backlinks(ref: str) -> dict[str, Any]:
        """Return canonical source dependencies for an entity page."""
        return result(service.backlinks, ref)

    @mcp.tool()
    def jobs(limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """List local job status with pagination."""
        return result(service.store.list_jobs, limit=limit, offset=offset)

    @mcp.tool()
    def get_job(job_id: str) -> dict[str, Any]:
        """Get one local job status."""
        return result(service.store.get_job, job_id)

    @mcp.tool()
    def ingest_path(path: str, rights: str = "unknown", idempotency_key: str | None = None) -> dict[str, Any]:
        """Ingest one configured-root local file; requires write capability."""
        return result(_write_job, "ingest_file", {"path": path, "rights": rights}, idempotency_key)

    @mcp.tool()
    def ingest_url(url: str, rights: str = "unknown", idempotency_key: str | None = None) -> dict[str, Any]:
        """Ingest one public HTTP(S) resource; requires write capability."""
        return result(_write_job, "ingest_url", {"url": url, "rights": rights}, idempotency_key)

    @mcp.tool()
    def export_compilation_request(revision_ids: list[str] | None = None) -> dict[str, Any]:
        """Export an evidence-bound agent request; requires write capability for its audit run."""
        return result(_write, service.compile_export, revision_ids)

    @mcp.tool()
    def apply_compilation_result(proposal: dict[str, Any]) -> dict[str, Any]:
        """Atomically import a validated agent proposal; requires write capability."""
        return result(_write, service.compile_apply, proposal)

    @mcp.tool()
    def render(include_unreviewed: bool = False, idempotency_key: str | None = None) -> dict[str, Any]:
        """Render deterministic Markdown projections; requires write capability."""
        return result(
            _write_job,
            "render",
            {"include_unreviewed": include_unreviewed},
            idempotency_key,
        )

    @mcp.tool()
    def refresh(source_id: str | None = None, idempotency_key: str | None = None) -> dict[str, Any]:
        """Refresh local sources and propagate targeted staleness; requires write capability."""
        return result(_write_job, "refresh", {"source_id": source_id}, idempotency_key)

    @mcp.tool()
    def rebuild_index() -> dict[str, Any]:
        """Rebuild local lexical indexes; requires write capability."""
        return result(_write, service.rebuild_index)

    @mcp.tool()
    def cancel_job(job_id: str) -> dict[str, Any]:
        """Cancel a queued local job; requires write capability."""
        return result(_write, service.cancel_job, job_id)

    @mcp.tool()
    def export_backup(relative_path: str) -> dict[str, Any]:
        """Write a versioned backup inside the wiki root; requires write capability."""
        return result(_file_operation, "export", relative_path)

    @mcp.tool()
    def import_backup(relative_path: str) -> dict[str, Any]:
        """Restore a versioned backup into an empty store; requires write capability."""
        return result(_file_operation, "import", relative_path)

    @mcp.tool()
    def migrate_markdown(relative_directory: str) -> dict[str, Any]:
        """Import patch-era Markdown as candidates; requires write capability."""
        return result(_file_operation, "markdown", relative_directory)

    @mcp.tool()
    def approve_claim(claim_revision_id: str, reviewer: str, note: str) -> dict[str, Any]:
        """Approve the exact candidate revision; requires independent review capability."""
        return result(_review, claim_revision_id, "approve", reviewer, note)

    @mcp.tool()
    def reject_claim(claim_revision_id: str, reviewer: str, note: str) -> dict[str, Any]:
        """Reject the exact candidate revision; requires independent review capability."""
        return result(_review, claim_revision_id, "reject", reviewer, note)

    @mcp.tool()
    def retract_claim(claim_revision_id: str, reviewer: str, note: str) -> dict[str, Any]:
        """Retract an exact reviewed revision; requires independent review capability."""
        return result(_review, claim_revision_id, "retract", reviewer, note)

    def _write(callable_, *args: Any) -> dict[str, Any]:
        require_write()
        return callable_(*args)

    def _write_job(kind: str, request: dict[str, Any], key: str | None) -> dict[str, Any]:
        require_write()
        return service.submit_job(kind, request, idempotency_key=key, wait=True)

    def _review(claim_revision_id: str, action: str, reviewer: str, note: str) -> dict[str, Any]:
        require_review()
        return service.review(claim_revision_id, action, reviewer=reviewer, note=note)

    def _wiki_path(value: str) -> Path:
        candidate = (service.config.root / value).resolve()
        if candidate != service.config.root and service.config.root not in candidate.parents:
            raise error("path_outside_wiki_root", "MCP file path escapes the configured wiki root.")
        return candidate

    def _file_operation(operation: str, value: str) -> dict[str, Any]:
        require_write()
        path = _wiki_path(value)
        if operation == "export":
            return service.export_json(path)
        if operation == "import":
            return service.import_json(path)
        return service.import_markdown(path)

    @mcp.resource("llmwiki://sources/{source_id}", mime_type="application/json")
    def source_resource(source_id: str) -> dict[str, Any]:
        """Canonical source and revision history."""
        return result(service.get_source, source_id)

    @mcp.resource("llmwiki://revisions/{revision_id}/nodes", mime_type="application/json")
    def tree_resource(revision_id: str) -> dict[str, Any]:
        """Top-level nodes for an immutable source revision."""
        return result(service.list_nodes, revision_id)

    @mcp.resource("llmwiki://revisions/{revision_id}", mime_type="application/json")
    def revision_resource(revision_id: str) -> dict[str, Any]:
        """Immutable source revision with extraction provenance."""
        return result(service.get_revision, revision_id)

    @mcp.resource("llmwiki://nodes/{node_id}", mime_type="application/json")
    def node_resource(node_id: str) -> dict[str, Any]:
        """Exact tree node content and evidence locator."""
        return result(service.read_node, node_id)

    @mcp.resource("llmwiki://pages/{ref}", mime_type="application/json")
    def page_resource(ref: str) -> dict[str, Any]:
        """Canonical page/entity projection data."""
        return result(service.get_page, ref)

    @mcp.resource("llmwiki://claims/{claim_revision_id}", mime_type="application/json")
    def claim_resource(claim_revision_id: str) -> dict[str, Any]:
        """Immutable claim revision, evidence, and review events."""
        return result(service.get_claim_revision, claim_revision_id)

    @mcp.resource("llmwiki://evidence/{evidence_id}", mime_type="application/json")
    def evidence_resource(evidence_id: str) -> dict[str, Any]:
        """One exact evidence locator and immutable source digest."""
        return result(service.get_evidence, evidence_id)

    @mcp.resource("llmwiki://reviews/pending", mime_type="application/json")
    def pending_reviews_resource() -> dict[str, Any]:
        """Pending candidate and disputed claim revisions."""
        return result(service.review_list)

    @mcp.resource("llmwiki://traces/{trace_id}", mime_type="application/json")
    def trace_resource(trace_id: str) -> dict[str, Any]:
        """Safe retrieval trace without hidden chain-of-thought."""
        return result(service.get_trace, trace_id)

    @mcp.resource("llmwiki://jobs/{job_id}", mime_type="application/json")
    def job_resource(job_id: str) -> dict[str, Any]:
        """Local job status and safe result."""
        return result(service.store.get_job, job_id)

    return mcp


def run_stdio(root: Path, *, allow_writes: bool = False, allow_review: bool = False) -> None:
    server = create_server(root, allow_writes=allow_writes, allow_review=allow_review)
    server.run(transport="stdio")
