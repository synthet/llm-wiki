"""llmwiki - tools to index, lint/validate, and search an LLM Wiki.

An LLM Wiki (Karpathy, 2026) is a set of durable, interlinked Markdown pages
that a model incrementally compiles from raw sources, accumulating synthesis,
contradictions and provenance over time. This package treats those pages as a
claim-centric, provenance-aware knowledge base and provides:

* a page/frontmatter model with review-state, sources, claims and freshness,
* an indexer (SQLite FTS5 when available, JSON inverted-index fallback),
* a full-text + wikilink search engine,
* a structural/semantic linter ("lint-validate"),
* a CLI (`llmwiki`) and an MCP server (`llmwiki-mcp`).

The public API is intentionally small and stable; see `llmwiki.cli` and
`llmwiki.mcp_server` for the two entry points.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .model import (  # noqa: F401
    PAGE_TYPES,
    STATUSES,
    Page,
    PageIssue,
)
from .wiki import Wiki  # noqa: F401

__all__ = ["__version__", "PAGE_TYPES", "STATUSES", "Page", "PageIssue", "Wiki"]
