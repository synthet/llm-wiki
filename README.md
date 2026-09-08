# LLM Wiki

LLM Wiki is a local-first, evidence-bound knowledge compiler for Python 3.11+. It stores immutable
source revisions and reviewed claims in SQLite, projects canonical knowledge to deterministic
Markdown, and exposes the same application services through a CLI and a maintained-SDK MCP server.

This is an early v1 core: suitable for local evaluation and small-team workflows, with no web UI,
distributed worker, OCR, semantic/vector search, or hosted service.

## Install

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix: source .venv/bin/activate
python -m pip install -e ".[dev]"
```

With [uv](https://docs.astral.sh/uv/):

```bash
uv sync --extra dev
uv run llmwiki --help
```

## Offline quick start

```bash
llmwiki init --root /path/to/wiki
llmwiki ingest /path/to/wiki/sources/notes.md --root /path/to/wiki
llmwiki compile --export-request request.json --root /path/to/wiki
# An external agent returns schema-valid, evidence-bound proposals in result.json.
llmwiki compile --apply-result result.json --root /path/to/wiki
llmwiki review list --root /path/to/wiki
llmwiki review approve CLAIM_REVISION_ID --reviewer "Name" --note "Evidence checked" --root /path/to/wiki
llmwiki render --root /path/to/wiki
llmwiki ask "What is supported by reviewed evidence?" --root /path/to/wiki
```

`agent` is the default provider mode and makes zero model-network calls. Every generated factual
claim starts as `candidate`; only an explicit, attributed human review event can promote the exact
revision to `reviewed`. Search and ask default to current reviewed claims.

## Commands

Core workflows: `init`, `ingest`, `sources`, `compile`, `ask`, `review list|approve|reject|retract`,
`refresh`, `render`, `export`, `import`, `jobs`, and `job get|cancel`.

Compatibility/projection commands: `new`, `index`, `search`, `lint`/`validate`, `stats`, `get`,
`list`, `links`, `rules`, and `mcp`. Pass `--json` before or after the command for compact JSON.
Exit codes are 0 success, 2 invalid input, 3 conflict/stale state, 4 missing record, 5 security or
capability rejection, and 6 provider failure. Long operations wait by default; supported commands
accept `--no-wait` and return a local job ID.

## Canonical storage

`.llmwiki/wiki.db` contains sources, UUID-identified immutable revisions, entities/aliases, claim
revisions, exact evidence locators, contradictions, dependencies, review events, compilation runs,
retrieval traces, render state, and jobs. Original bytes live under content-addressed
`.llmwiki/objects/<prefix>/<sha256>`. Titles, paths, filenames, and slugs are aliases—not identity.

Generated `wiki/pages/*.md` files are deterministic projections. Handwritten notes belong in
`wiki/notes/`. A stored file digest prevents silent overwrite after a generated page is manually
edited. Search indexes and document trees are rebuildable from canonical records and immutable
bytes. See [architecture](docs/architecture.md), [schema](docs/schema.md), and
[backup/migration](docs/backup-and-migration.md).

## Ingestion and retrieval

V1 accepts UTF-8 Markdown/plain text, text-based PDF through `pypdf`, and one explicitly supplied
HTTP(S) resource (no crawling). Image-only/no-text PDFs return `ocr_required`. Markdown headings,
plain-text headings, PDF outlines/pages, sections, and paragraphs form a deterministic local tree.
Retrieval uses SQLite FTS5 when available and identifies the deterministic Python lexical fallback
when it is not. Evidence always resolves to exact line/character or PDF page/character bounds.

## Provider modes

- `agent` (default): export a bounded request and validate a later result; zero model calls.
- `api`: call only the explicitly configured OpenAI-compatible endpoint.
- `local`: allow only an explicitly configured loopback OpenAI-compatible endpoint and reject URL
  ingestion. No mode, endpoint, or provider is selected as a fallback.

Configuration is explicit through `--mode`, `--endpoint`, `--compiler-model`, and
`--api-key-env` (or the corresponding `LLMWIKI_*` environment variables). Credentials are read by
environment-variable name; never put a token in a repository config or command argument.

## MCP

`llmwiki mcp --root /absolute/wiki/path` runs stdio using the official maintained Python `mcp` SDK.
Diagnostics stay off protocol stdout. Read/search tools are available by default. Ingestion,
compilation, refresh, rendering, migration, and cache writes need `--allow-writes`; review changes
need the independent `--allow-review` flag. Neither capability implies the other.

Project templates are in `.mcp.json`, `.cursor/mcp.example.json`, and `.codex/config.toml`.
Cross-platform installed and checkout-based examples are in [MCP/editor setup](docs/mcp-and-editors.md).

## Security and privacy

Local documents are untrusted data. Their macros, shell fragments, prompt-like instructions, and
embedded commands are never executed. Local paths must resolve inside configured roots; symlink
escapes are rejected. URL acquisition validates every redirect, streams through byte limits,
disables proxy environment inheritance, and blocks non-public/loopback/link-local/metadata-style
destinations plus resolution changes. PDF and download sizes/pages/time are bounded.

No PageIndex package, code, credentials, service, telemetry, or network endpoint is used. The local
hierarchical retrieval design is independent. See [security](docs/security.md) for the threat model
and known limits.

## Development

```bash
uv sync --extra dev
uv run ruff check .
uv run python -m pytest -q
uv run python scripts/sync_assistant_trees.py --check
uv run python scripts/generate_agent_asset_inventory.py --check
uv run python scripts/ci/check_agent_frontmatter.py
uv run python scripts/ci/check_secrets.py
uv run python scripts/okf_lint.py --profile project --exclude-prefix archive/ docs
```

Live remote/local-provider tests are intentionally opt-in and are not part of the offline default
suite. The repository is based on `synthet-code-framework`; that framework is not a runtime
dependency or required sibling checkout.

## License

MIT. Third-party dependencies retain their own licenses.
