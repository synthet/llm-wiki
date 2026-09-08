# Implement the Local-First LLM Wiki

## Summary

Build a Python 3.11+ knowledge compiler in [synthet/llm-wiki](https://github.com/synthet/llm-wiki), using these references:

- `D:\Downloads\llmwikitoolkit.patch` as an audited implementation starter.
- `D:\Downloads\deep-research-report (4).md` as product and architecture research.
- [VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex) for hierarchical, vectorless retrieval concepts.
- [VectifyAI/pageindex-mcp](https://github.com/VectifyAI/pageindex-mcp) for MCP schemas, resources, document validation, bounded retries, and actionable errors.

The finished core must ingest local sources, retain immutable evidence, compile candidate claims into linked Markdown, support human review, detect stale knowledge, retrieve evidence through local hierarchical trees, and expose the same operations through CLI and MCP.

PageIndex is a conceptual reference only. Do not install PageIndex packages, connect to PageIndex services, upload documents, use PageIndex authentication, or claim PageIndex compatibility.

## Implementation

### Foundation and storage

- Recheck the target repository and preserve unrelated changes. Reconcile its existing README with the patch instead of overwriting it blindly.
- Audit and adapt the patch's useful Python package, CLI, FTS search, linter, agent integrations, tests, and sample wiki. Treat its claimed test results as unverified.
- Use SQLite transactions as the canonical store for sources, revisions, entities, claims, claim revisions, evidence, contradictions, dependencies, review events, compilation runs, and jobs.
- Use persisted UUID4 identifiers for logical objects. Identify immutable source revisions by actual SHA-256 digests. Titles, filenames, and slugs remain aliases.
- Store original source bytes under content-addressed paths. Key extracted text and document-tree artifacts by source digest, parser version, index format version, and configuration digest.
- Render `wiki/pages/*.md` deterministically from canonical records. Keep handwritten material under `wiki/notes/`. Detect manual edits to generated pages and stop with a recoverable conflict.
- Add an explicit migration command for patch-era Markdown pages. Preserve original files, import their identities where valid, and leave unverifiable content as candidate knowledge.
- Use safe PyYAML parsing. Remove the handwritten YAML fallback parser.
- Provide versioned JSON export/import and documented backup/restore. Search indexes, trees, and rendered pages must be rebuildable.

### Ingestion and evidence

- Support UTF-8 Markdown, plain text, text-based PDF, and explicitly supplied HTTP(S) URLs. URL ingestion fetches one resource without crawling.
- Use `pypdf` for PDF text, bookmarks, and page boundaries. Detect image-only PDFs and return `ocr_required`; OCR is outside v1.
- Record source identity, revision digest, original URI/path, acquisition time, media type, parser version, rights metadata, and extraction provenance.
- Evidence must reference one immutable revision and a validated locator:
  - Text/Markdown: line and character boundaries.
  - PDF: page plus character boundaries within extracted page text.
- Reingesting identical bytes must reuse the revision and avoid unnecessary parsing or model calls. Changed bytes create a new revision under the same source identity.
- Keep rights unknown unless supplied or verified. Do not infer document rights from software licenses.
- Validate file type using content signatures, enforce configurable byte/page/time limits, prevent path and symlink escapes, stream downloads through size limits, validate redirects, and protect URL ingestion from SSRF.
- Treat document content as untrusted data and never execute embedded instructions.

### Model modes and compilation

Provide one provider interface with three explicit modes:

- `agent`, the default: the toolkit makes no LLM call. It exports evidence-bound requests for an external agent and validates returned proposals.
- `api`: call a configured OpenAI-compatible remote endpoint using environment-supplied credentials.
- `local`: call only an OpenAI-compatible loopback endpoint. Reject remote model endpoints, URL ingestion, and any other outbound network access.

Allow separate compiler and retrieval models. Never switch provider or mode automatically.

For API and local modes:

- Enforce request, token, time, and retry budgets.
- Retry only transient failures.
- Require schema-valid structured output.
- Record provider, model, prompt digest, configuration digest, input revisions, timestamps, and available usage data.
- Never invent cost information.

For agent mode:

- Export a versioned request containing a run ID, canonical-state version, source revisions, evidence bundle, expected schema, and limits.
- Import proposals only when the run ID, state version, source revisions, identities, and evidence locations still match.
- Reject stale or malformed proposals without partially changing canonical state.

Compilation must:

1. Extract atomic candidate claims.
2. Resolve entities conservatively.
3. Attach exact evidence.
4. Compare new claims with existing claims.
5. Retain disagreements as contradiction records.
6. Update only dependent entities and pages.
7. Render deterministic Markdown projections.

All generated claims begin as `candidate`. Ambiguous entity matches remain unresolved. Failed or interrupted runs must commit nothing or remain transactionally resumable.

### Review, provenance, and freshness

Support `candidate`, `reviewed`, `disputed`, `stale`, `superseded`, and `retracted`.

- Promotion requires an explicit review event with reviewer, timestamp, rationale, and exact claim revision.
- Automated validation cannot grant reviewed status.
- A changed source revision marks its dependent current claims stale without affecting unrelated claims.
- Recompilation produces new candidate revisions requiring review.
- Preserve historical claim text, evidence, review decisions, contradictions, supersessions, and retractions.
- Default search and answers to current reviewed claims. Candidate, disputed, and stale content may be included only through explicit filters and must retain visible status labels.
- Strengthen validation to check complete digests against stored bytes, locator bounds, evidence references, identity uniqueness, field types, state transitions, dependency consistency, and reviewed-content requirements.

### Independent hierarchical retrieval

Build a local hierarchical document tree without PageIndex code or dependencies.

Each tree node contains:

- Stable node ID and source revision ID.
- Parent and ordered child IDs.
- Depth and document order.
- Heading or deterministic label.
- Optional generated summary.
- Exact page, line, and character bounds.
- Content digest and token estimate.

Construct structure from Markdown headings, PDF bookmarks, detected headings, pages, paragraphs, and lists. For unstructured documents, use deterministic page and paragraph grouping. Model-generated summaries may enrich nodes but cannot replace source text or evidence boundaries.

Retrieval proceeds as follows:

1. Use metadata and lexical search to select candidate documents.
2. Traverse their trees from broad sections to narrow nodes.
3. Read exact leaf content only after branch selection.
4. Return evidence tied to immutable revisions.

In API/local modes, the configured model may select branches within strict depth, node, token, request, and time limits. In agent mode, expose traversal tools so the external agent performs the reasoning.

Record selected nodes, scores, retrieval method, and concise supplied decision summaries. Do not request or store hidden chain-of-thought. Return structured insufficiency when evidence is inadequate. Keep FTS5 with a pure-Python lexical fallback and identify the backend used.

### Public interfaces

Retain the useful patch commands and add:

- `llmwiki ingest`
- `llmwiki sources`
- `llmwiki compile`
- `llmwiki compile --export-request`
- `llmwiki compile --apply-result FILE`
- `llmwiki ask`
- `llmwiki review list|approve|reject|retract`
- `llmwiki refresh`
- `llmwiki render`
- `llmwiki export`
- `llmwiki import`
- `llmwiki jobs`
- `llmwiki job get|cancel`

Commands must support consistent JSON output, stable exit codes, actionable errors, and wiki-root discovery. Long CLI operations wait by default and support `--no-wait`.

Use the maintained Python MCP SDK with stdio transport. Keep protocol stdout clean and share application services with the CLI.

Expose read-only resources for sources, revisions, document trees, nodes, pages, claims, evidence, and pending reviews. Use stable `llmwiki://` URIs, resource templates, pagination, and response limits.

Expose read-only tools by default:

- Search, ask, list/get pages and sources.
- Read/search document-tree nodes.
- Retrieve evidence and traversal traces.
- Validate, inspect statistics, backlinks, and jobs.

Expose ingestion, compilation, refresh, rendering, and import only with `--allow-writes`. Expose review changes only with `--allow-review`. Write authority must not imply review authority.

Validate tool arguments before application logic. Return structured content plus concise text. Use a stable error object containing `code`, `message`, safe `details`, `retryable`, and `next_steps`.

Represent long MCP operations as idempotent local jobs with `queued`, `running`, `completed`, `failed`, and `cancelled` states.

Update Claude Code, Cursor, and Gemini integrations to use the implemented CLI/MCP contracts. Document Windows, Unix, checkout-based, and installed-command configurations without assuming the client's working directory.

## Test Plan

Use deterministic fixtures and a fake provider in default CI. Test:

- Clean install, migration from patch pages, backup/restore, and deterministic rerendering.
- Duplicate ingestion, changed revisions, actual digest verification, Unicode titles, slug collisions, and ambiguous aliases.
- Valid and invalid text/PDF locators, invalid PDFs, image-only PDFs, size limits, redirect SSRF, symlink escapes, and interrupted ingestion.
- No-op incremental compilation, invalid model output, provider failures, request budgets, atomic transactions, contradictions, and targeted stale propagation.
- Agent request/result round trips, stale-result rejection, and zero model calls in agent mode.
- Local mode allowing loopback model calls while blocking remote endpoints, URL ingestion, DNS, and dependency-level network fallback.
- Deterministic document trees, valid node boundaries, revision isolation, bounded traversal, insufficiency results, and identified lexical fallback.
- Reviewed-only filtering through lexical search, tree traversal, link expansion, and answers.
- Review audit history and independent MCP write/review capability gates.
- MCP initialization, typed schemas, resource templates, pagination, root boundaries, clean stdout, idempotent jobs, and redacted errors.
- Package manifests and lock files containing no PageIndex dependency; ordinary offline workflows making no connection to PageIndex or any hosted service.
- A real stdio MCP integration flow that ingests a local fixture, explores its tree, retrieves evidence, imports an externally produced candidate, renders Markdown, reviews it, and returns a cited answer without network access.

Add a small evaluation corpus for citation coverage, locator validity, expected support, contradiction retention, retrieval faithfulness, review leakage, and unrelated-page stability. Required deterministic thresholds must gate CI; model-dependent semantic evaluations are reported separately.

Validate on Windows and Linux. Keep live API/local-provider tests opt-in and report skipped checks when configuration is absent.

## Assumptions and exclusions

- This is a working CLI/MCP core for individuals and small teams; no web UI.
- No PageIndex package, SDK, MCP package, hosted endpoint, API key, OAuth, upload, telemetry, or transitive cloud dependency is permitted.
- PageIndex names appear only in attribution and design documentation.
- API mode may use a user-configured remote model provider; agent and local workflows remain usable without one.
- HTTP source ingestion is permitted outside local mode and is always explicit.
- OCR, distributed workers, model training, CKAN, DVC/MLflow, Google OKF, RO-Crate, DCAT, Croissant, SPDX exports, hosting, and publishing remain future work.
- The research report is imported as an immutable source revision. Its claims remain candidate unless separately verified and reviewed.
- Complete local implementation and verification are included. Pushing, merging, releasing, or publishing requires separate authorization.
