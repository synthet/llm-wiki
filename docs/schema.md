---
type: Technical Reference
title: Canonical Schema
description: SQLite records, evidence locators, state transitions, and version contracts.
resource: schema.md
tags: [docs, schema, sqlite, provenance]
timestamp: 2026-09-07T00:00:00Z
okf_version: 0.1
---

# Canonical schema

Schema version is stored in `schema_migrations`; the current version is 1. JSON backup format and
agent request format are independently versioned at 1.

| Record | Purpose |
|---|---|
| `sources` | Logical source identity, alias/URI, rights, current revision |
| `source_revisions` | Immutable UUID, SHA-256, object path, extraction/provenance/version keys |
| `entities`, `entity_aliases` | Canonical entity UUID and potentially ambiguous names |
| `claims`, `claim_revisions` | Logical claim and immutable text revision/lifecycle |
| `evidence` | Exact locator/quote to one immutable source revision |
| `contradictions` | Retained disagreement between exact claim revisions |
| `dependencies` | Claim-revision → source-revision freshness edges |
| `review_events` | Reviewer, action, note, before/after state, timestamp |
| `compilation_runs` | Mode/provider/model, prompt/config/input digests, usage when available |
| `document_nodes` | Ordered local hierarchy with exact bounds/digest/token estimate |
| `retrieval_traces` | Selected node IDs, method/backend, concise summary and results |
| `render_state` | Canonical and file digests used for conflict detection |
| `jobs` | Idempotent local work in queued/running/completed/failed/cancelled states |

## Evidence locators

Text/Markdown locators use 1-based inclusive `line_start`/`line_end` and 0-based half-open
`char_start`/`char_end` over stored extracted UTF-8 text. The line and character ranges must agree.
PDF locators use a 1-based page and 0-based half-open character bounds within that page's stored
extracted text. An evidence quote must equal the resolved substring exactly.

## Claim lifecycle

States: `candidate`, `reviewed`, `disputed`, `stale`, `superseded`, `retracted`.

- Candidate → reviewed/disputed/stale/retracted.
- Reviewed → disputed/stale/superseded/retracted.
- Disputed → reviewed/stale/superseded/retracted.
- Stale → superseded/retracted.
- Superseded and retracted are terminal.

Status events are auditable. Text is never overwritten. A replacement references
`supersedes_revision_id`, makes the prior revision non-current, and begins as a candidate.

## Versions and rebuildability

Extraction artifacts are keyed by source digest, parser version, tree-format version, and relevant
configuration digest. FTS tables are caches, not exported truth. Trees, indexes, and rendered pages
can be rebuilt from SQLite records and verified immutable object bytes.

