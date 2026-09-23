---
type: Technical Reference
title: LLM Wiki Technical Reference
description: Comprehensive technical specification of the LLM Wiki storage engine, knowledge compiler, locator resolution, semantic retrieval, and tool interfaces.
resource: docs/technical-reference.md
tags: [docs, technical-reference, llmwiki, architecture, retrieval, okf]
timestamp: 2026-09-23T00:15:00Z
okf_version: 0.1
---

# LLM Wiki technical reference

## 1. System overview and invariants

LLM Wiki is a local-first, evidence-bound knowledge compiler and retrieval engine. It bridges unstructured documents (Markdown, plain text, PDFs) and structured, queryable knowledge while maintaining strict provenance guarantees.

```text
Source Document (Bytes)
   │
   ▼
[Ingestion & Storage] ──► Content-Addressed Storage (.llmwiki/objects/)
   │                      + Document Tree Generation (UUID5 hierarchy)
   ▼
[Compilation Export]  ──► State-Versioned Agent Extraction Request
   │
   ▼
[Compilation Apply]   ──► Atomic Locator Verification + Evidence Binding
   │                      + Candidate Claim Insertion (SQLite .llmwiki/wiki.db)
   ▼
[Human Review]        ──► Attributed Promotion: candidate ──► reviewed
   │
   ▼
[Deterministic Render]──► Generated Markdown Projection (wiki/pages/<slug>.md)
   │
   ▼
[Hybrid Retrieval]    ──► FTS5 Lexical Search + TypeSafe Jev Semantic Reranking
```

### Core invariants

1. **Canonical store vs. projections**: SQLite (`.llmwiki/wiki.db`) and content-addressed objects (`.llmwiki/objects/`) are canonical truth. Markdown files under `wiki/pages/` are strictly generated projections and must never be edited manually.
2. **Exact evidence binding**: Every generated claim must cite an immutable source revision UUID and an exact contiguous character/line locator (`validate_locator`) that re-resolves the verbatim quote string.
3. **Dual-confidence & review separation**: All generated claims enter the system with `candidate` status. Only an attributed human review operation (`llmwiki review approve`) may promote a claim to `reviewed`. Write authority and review authority remain strictly separated.
4. **Reviewed-only retrieval default**: Search and QA operations (`llmwiki search`, `llmwiki ask`) query only `reviewed` claims by default. Querying unreviewed data requires explicit opt-in (`--include-status candidate`).
5. **No silent remote fallbacks**: Agent mode performs zero model calls. Local mode permits only local loopback endpoints. The system never silently falls back to remote cloud APIs.

---

## 2. Storage architecture & schema

The storage layer consists of an embedded SQLite database and a directory of content-addressed raw source blobs.

### File layout

```text
.llmwiki/
├── config.yaml          # Root paths, allowed_roots, provider configuration
├── wiki.db              # Canonical SQLite database (WAL mode)
└── objects/             # Content-addressed source storage
    └── ab/
        └── cd...        # SHA-256 named source byte blobs
```

### Core tables

| Table | Identity | Purpose |
| :--- | :--- | :--- |
| `sources` | UUID4 | Logical source identities with display names and original URIs. |
| `source_revisions` | UUID4 | Immutable snapshot of source bytes with SHA-256 digest, extracted text, and parser metadata. |
| `document_nodes` | UUID5 | Hierarchical document structure (headings, sections, paragraphs) keyed to revision. |
| `entities` | UUID4 | Normalized knowledge concepts with unique URL-safe slugs. |
| `entity_aliases` | Normalized text | Alternate names mapping to canonical entity IDs. |
| `claims` | UUID4 | Logical assertion container belonging to an entity. |
| `claim_revisions` | UUID4 | Versioned assertion text, status (`candidate`, `reviewed`, `superseded`, `disputed`), and content hash. |
| `evidence` | UUID4 | Link between a claim revision and a source revision with exact JSON locator and verbatim quote. |
| `dependencies` | Composite | Direct dependency edges mapping claim revisions to source revisions for freshness invalidation. |
| `contradictions` | UUID4 | Explicit disagreement records between conflicting claim revisions. |
| `review_events` | UUID4 | Immutable audit log of human approval/rejection operations with reviewer notes. |
| `compilation_runs` | UUID4 | Records of compilation exports, input revisions, state versions, and applied results. |
| `retrieval_traces` | UUID4 | Audit trail of search executions, candidate pools, and reranking scores. |
| `claim_fts` / `node_fts` | SQLite FTS5 | Full-text virtual tables providing BM25 lexical candidate retrieval. |

---

## 3. Ingestion & document hierarchy

### Bounded ingestion (`src/llmwiki/ingest.py`)
- Ingestion enforces path containment against `allowed_roots` defined in `.llmwiki/config.yaml`.
- Computes SHA-256 byte digest and stores raw bytes in `.llmwiki/objects/<hash[:2]>/<hash[2:]>`.
- Extracts plain text, structural headers, and metadata across Markdown, UTF-8 text, and PDF formats.

### Hierarchical document trees (`src/llmwiki/tree.py`)
- Deconstructs source text into a deterministic tree of `document_nodes`.
- Generates stable UUID5 node identifiers derived from revision ID, tree depth, document order, and heading text.
- Nodes maintain exact character and line bounds within the parent document.

---

## 4. Knowledge compilation & evidence validation

Compilation translates source text into structured entity claims through an atomic, evidence-bound protocol.

```text
1. compile_export([revision_ids])
   └── Captures current state_version and input revision digests.
   └── Creates compilation_runs record with status 'exported'.

2. External Agent / Model Synthesis
   └── Proposes candidate claims with entity name, claim text, and exact evidence quotes.

3. compile_apply(payload)
   └── Validates payload.version == 1 and payload.state_version == current_state_version.
   └── Verifies each evidence locator: text[char_start:char_end] == quote.
   └── Resolves or creates entity identities and slugs.
   └── Records claims, claim_revisions, evidence, and dependencies.
   └── Increments state_version and updates FTS5 search index.
```

### Locator validation rule (`src/llmwiki/domain.py`)
Text locators must satisfy:
$$\text{locator} = \{\text{kind: 'text'}, \text{char\_start}: s, \text{char\_end}: e, \text{line\_start}: l_s, \text{line\_end}: l_e\}$$
$$\text{extracted\_text}[s:e] \equiv \text{quote}$$
$$\text{count}(\text{'\textbackslash n'}, 0, s) + 1 = l_s \quad \text{and} \quad \text{count}(\text{'\textbackslash n'}, 0, \max(s, e-1)) + 1 = l_e$$

Any discrepancy between character offsets and line numbers fails closed with `evidence_quote_mismatch` or `invalid_locator`.

---

## 5. Hybrid retrieval & semantic reranking

Retrieval combines fast lexical indexing with semantic reranking to optimize precision across large knowledge collections.

```text
User Query
   │
   ▼
[Stage 1: Lexical Candidate Pool]
   └── SQLite FTS5 BM25 search over claim_fts / node_fts (candidate_pool = 50)
   │
   ▼
[Stage 2: Semantic Reranking]
   └── TypeSafe Jev / System One semantic evaluation (jev_score / jev_choice)
   │
   ▼
[Stage 3: Citation & Provenance Resolution]
   └── Resolves entity names, claim status, exact evidence quotes, and source digests
   │
   ▼
Structured Output + Retrieval Trace (.llmwiki/wiki.db: retrieval_traces)
```

- **Insufficiency gating**: If retrieved candidates do not satisfy query relevance thresholds or if no reviewed evidence exists, the service returns `insufficient: true` rather than hallucinating unsupported answers.
- **Traceability**: All retrieval operations record an immutable `retrieval_traces` entry documenting candidate IDs, scores, and execution parameters.

---

## 6. Projection & deterministic rendering

The rendering engine (`src/llmwiki/render.py`) generates human-readable Markdown pages in `wiki/pages/<slug>.md`.

- **Deterministic ordering**: Claims are sorted by status (`reviewed` first, then `candidate`), creation timestamp, and claim revision ID.
- **Integrity protection**: Each rendered file begins with a header comment:
  ```markdown
  <!-- Generated by llmwiki; edit canonical records, not this file. -->
  <!-- llmwiki-render:<canonical_digest> -->
  ```
- **Conflict detection**: Before writing to disk, `render` checks if the existing file on disk matches `<canonical_digest>`. If an external process manually modified the file, rendering halts with a recoverable `render_conflict`.

---

## 7. Interfaces: CLI, MCP, and OKF tooling

### CLI surface (`src/llmwiki/cli.py`)
```bash
uv run llmwiki ingest <path>              # Acquire and extract source documents
uv run llmwiki compile --export-request   # Generate compilation request bundle
uv run llmwiki compile --apply-result    # Apply validated compilation results
uv run llmwiki review approve <claim_id>  # Human review promotion to 'reviewed'
uv run llmwiki render --include-unreviewed # Project store to wiki/pages/*.md
uv run llmwiki search <query>             # Query reviewed knowledge with FTS5/Jev
uv run llmwiki ask <question>             # Evidence-backed synthesis and answers
uv run llmwiki validate                   # Audit database invariants and locators
uv run llmwiki stats                      # Report store metrics and status counts
```

### Model Context Protocol (MCP) server (`src/llmwiki/mcp_server.py`)
Exposes stdio MCP tools for coding agents:
- `search`: Hybrid lexical and semantic search.
- `ask`: Structured, citation-backed knowledge answering.
- `get_entity` / `list_entities`: Knowledge graph entity traversal.
- `read_source` / `list_sources`: Content-addressed document access.
- `ingest_path` / `compile` / `review` / `render`: Write operations (when `--allow-writes` is enabled).

### OKF bundle integration
The repository documentation tree (`docs/`) conforms to the Open Knowledge Format (OKF v0.1):
- Every concept page carries structured YAML frontmatter (`type`, `title`, `description`, `resource`, `tags`, `timestamp`, `okf_version`).
- Validated via `python scripts/okf_lint.py --profile project` and `python scripts/wiki_lint.py`.

---

## Related documentation

- [architecture.md](architecture.md) — High-level architecture and boundaries
- [schema.md](schema.md) — Database schema definition and migration rules
- [security.md](security.md) — Threat modeling and security boundaries
- [OKF_ADOPTION.md](OKF_ADOPTION.md) — Open Knowledge Format profile and rules
- [mcp-and-editors.md](mcp-and-editors.md) — Editor and MCP server configuration
