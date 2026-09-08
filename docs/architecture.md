---
type: Architecture
title: LLM Wiki Architecture
description: Canonical store, service boundaries, compilation, rendering, and retrieval flows.
resource: architecture.md
tags: [docs, architecture, llmwiki]
timestamp: 2026-09-07T00:00:00Z
okf_version: 0.1
---

# Architecture

LLM Wiki is an auditable knowledge compiler. Markdown is an output, not the database.

```text
source bytes → immutable revision/extraction → document tree
             → evidence-bound candidate claims → human review
             → current reviewed claims → deterministic Markdown
             → CLI and MCP retrieval/answers
```

## Boundaries

| Module | Responsibility |
|---|---|
| `domain.py` | Versions, digests, locators, and allowed state transitions |
| `store.py` | SQLite schema, migrations, transactions, jobs, and export rows |
| `ingest.py` | Bounded local/URL acquisition, media sniffing, text/PDF extraction |
| `tree.py` | Independent deterministic hierarchy and exact node boundaries |
| `providers.py` | Explicit agent/API/local provider contracts and budgets |
| `service.py` | Shared application workflows and canonical mutations |
| `render.py` | Deterministic Markdown and manual-edit conflict checks |
| `cli.py` / `mcp_server.py` | Transport, argument validation, capability gates, safe errors |

CLI and MCP never implement business state transitions independently. They call `WikiService`.

## Transactions and identity

Logical objects use persisted UUID4 identifiers. A source revision has its own UUID and an actual
SHA-256 over original bytes. Source bytes are written to a content-addressed object path and
verified before the revision transaction completes. Schema migration 1 is applied under
`BEGIN IMMEDIATE`; a database newer than the supported schema fails closed.

Titles, aliases, slugs, paths, and URIs are lookup names. They do not replace UUID identity.
Aliases may be ambiguous; ambiguous resolution is returned as an error instead of forced merging.

## Compilation and review

Agent mode records a run and exports a bounded request containing the canonical state version,
revision UUID/digest pairs, exact node text/locators, and the response schema. Import validates the
run, unchanged state version, current revision/digest identity, exact quotes, locators, entities,
and contradictions in one transaction. API/local adapters use the same request/result boundary.

Generated facts start `candidate`. Superseding creates a new claim revision and preserves the old
revision. Contradictions are first-class records. Review promotion requires a named reviewer, note,
timestamp, exact revision, valid evidence, and verified source bytes. No model grants review status.

## Freshness and rendering

When bytes change under a logical source, a new immutable revision becomes current. Only current
claim revisions depending on the prior revision become `stale`; unrelated claims are untouched.
Recompilation creates candidates requiring review.

`wiki/pages/<slug>.md` is rendered from canonical entities, current claims, and evidence in stable
order. Before replacement, the stored file digest must match the file on disk. A mismatch produces
a recoverable `render_conflict`. Handwritten content belongs in `wiki/notes/`.

## Retrieval

Tree nodes are keyed to one immutable revision and contain stable UUID5 node identity, parent,
depth, document order, heading, exact locator, content digest, and token estimate. Markdown uses
heading nesting; plain text uses deterministic detected headings; PDFs use pages, available
outlines, and paragraphs. Summaries are optional enrichment and never evidence.

Retrieval first ranks canonical reviewed claims with SQLite FTS5 (or the named Python lexical
fallback), then can traverse source trees and read exact leaves. Bounds and result sizes are capped.
Traces contain node IDs, scores/backend, and a concise decision summary—not hidden chain-of-thought.
Inadequate reviewed evidence returns a structured insufficiency result.

