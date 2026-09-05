# LLM Wiki

Tools to **index, lint-validate and search** an *LLM Wiki* — durable,
interlinked Markdown pages that a model incrementally compiles from raw sources,
accumulating synthesis, contradictions and provenance over time
([Karpathy, 2026](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)).

Unlike query-time RAG, an LLM Wiki does the work at *compile time* and leaves a
durable, auditable artifact. This repo treats that artifact as a **claim-centric,
provenance-aware knowledge base** and ships:

- **`llmwiki` CLI** — `index`, `search`, `lint`/`validate`, `new`, `stats`,
  `get`, `list`, `links`.
- **`llmwiki-mcp` MCP server** — the same operations as MCP tools, over stdio.
- **Editor/agent integrations** — [Claude Code](#claude-code),
  [Cursor](#cursor) and [Gemini CLI](#gemini-cli): skills, commands, rules and
  MCP config, all pre-wired.
- **A sample wiki** under [`wiki/`](wiki/pages) derived from the research
  baseline, plus tests.

Zero hard runtime dependencies: PyYAML is used when installed (with a stdlib
fallback parser), and the MCP server is pure standard library. SQLite **FTS5**
powers search when available, with a pure-Python BM25 fallback otherwise.

---

## Quick start

```bash
# From the repo root — no install needed:
export PYTHONPATH=src

python3 -m llmwiki.cli --root wiki lint --strict      # validate the wiki
python3 -m llmwiki.cli --root wiki index              # build the search index
python3 -m llmwiki.cli --root wiki search "OKFN vs OKF" --expand
python3 -m llmwiki.cli --root wiki get "Open Knowledge Format"
python3 -m llmwiki.cli --root wiki stats
```

Or install it and drop the `PYTHONPATH`/`python -m` prefix:

```bash
pip install -e ".[yaml]"     # provides `llmwiki` and `llmwiki-mcp`
llmwiki --root wiki search "provenance"
```

Start a fresh wiki anywhere:

```bash
llmwiki init my-wiki
llmwiki --root my-wiki new "My First Entity" --type entity
llmwiki --root my-wiki lint
```

---

## CLI

| Command | Purpose |
|---|---|
| `llmwiki init [dir]` | Scaffold a new wiki (`pages/`, `wiki.yaml`, index page). |
| `llmwiki new "Title" [--type] [--status] [-o]` | Create a page from the template. |
| `llmwiki index [--json]` | (Re)build the search index. |
| `llmwiki search Q [--limit] [--status] [--type] [--expand] [--json]` | Full-text + wikilink search. |
| `llmwiki lint` / `validate` `[--strict] [--json]` | Validate structure & provenance. Exit 1 on errors. |
| `llmwiki stats [--json]` | Health metrics (citation coverage, broken links, orphans). |
| `llmwiki get REF [--no-body] [--json]` | Print a page by id/slug/title/alias. |
| `llmwiki list [--status] [--type] [--tag] [--json]` | List pages. |
| `llmwiki links REF [--json]` | Backlinks and outbound links of a page. |
| `llmwiki rules` | List all linter rules. |
| `llmwiki mcp` | Run the MCP server over stdio. |

Every command auto-discovers the nearest wiki root, or takes `--root DIR`.
Add `--json` for machine-readable output.

---

## MCP server

`llmwiki-mcp` (or `llmwiki mcp`, or `python -m llmwiki.mcp_server`) speaks the
Model Context Protocol over stdio and exposes:

| Tool | Description |
|---|---|
| `wiki_search` | Full-text + wikilink search; ranked pages with snippets. |
| `wiki_get_page` | Fetch one page: claims, sources, links, body. |
| `wiki_list_pages` | List pages, filter by status/type/tag. |
| `wiki_validate` | Lint-validate; `ok=false` means errors. |
| `wiki_index` | Rebuild the index. |
| `wiki_stats` | Wiki health metrics. |
| `wiki_backlinks` | Local wikilink graph around a page. |

The wiki root is chosen from the tool argument `root`, else `$LLMWIKI_ROOT`, else
auto-discovery. Register it with any MCP client, e.g.:

```json
{
  "mcpServers": {
    "llmwiki": {
      "command": "python3",
      "args": ["-m", "llmwiki.mcp_server"],
      "env": { "PYTHONPATH": "src", "LLMWIKI_ROOT": "wiki" }
    }
  }
}
```

---

## Editor & agent integrations

All three are pre-configured in this repo and point at the same MCP server + CLI.

### Claude Code
- `CLAUDE.md` — project rules and invariants.
- `.claude/skills/llm-wiki/SKILL.md` — the compile/review/search skill.
- `.claude/commands/` — `/wiki-search`, `/wiki-lint`, `/wiki-index`,
  `/wiki-new`, `/wiki-review`.
- `.mcp.json` — registers the `llmwiki` MCP server.

### Cursor
- `.cursor/rules/llm-wiki.mdc` (always applied) and `wiki-authoring.mdc`
  (globbed to `wiki/**/*.md`).
- `.cursor/commands/` — `wiki-search`, `wiki-lint`, `wiki-index`.
- `.cursor/mcp.json` — registers the MCP server.

### Gemini CLI
- `GEMINI.md` — context/rules.
- `.gemini/settings.json` — registers the MCP server.
- `.gemini/commands/wiki/` — `/wiki:search`, `/wiki:lint`, `/wiki:index`,
  `/wiki:new` (TOML custom commands).

> The integrations invoke the toolkit as `PYTHONPATH=src python3 -m llmwiki.cli`
> so they work without installing. After `pip install -e .`, you can simplify
> them to plain `llmwiki` / `llmwiki-mcp`.

---

## The page model

Pages are Markdown with YAML frontmatter carrying claim-level provenance:

```yaml
---
id: entity:open-knowledge-format     # canonical identity (not the filename)
title: Open Knowledge Format
type: entity                         # entity | topic | note | index
slug: open-knowledge-format
status: reviewed                     # candidate|reviewed|disputed|stale|superseded|retracted
aliases: [OKF, Google OKF]
tags: [format, interoperability]
sources:
  - id: source:okf-repo
    uri: https://github.com/GoogleCloudPlatform/open-knowledge-format
    digest: sha256:<hex>
    rights: apache-2.0
claims:
  - id: claim:okf-is-format-not-platform
    text: OKF formalises the LLM-wiki pattern as portable Markdown + metadata.
    status: reviewed
    confidence: 0.9
    evidence:
      - source_id: source:okf-repo
        locator: {type: document}
freshness: {checked_at: 2026-09-05T00:00:00Z, stale: false}
rights: {license_expression: Apache-2.0, redistribution_allowed: true}
---
# Open Knowledge Format

Body with [[Wikilinks]] to related pages.
```

See [`docs/schema.md`](docs/schema.md) for the full spec and
[`docs/architecture.md`](docs/architecture.md) for how the toolkit is built.

### Invariants the linter enforces
1. Valid frontmatter with `id`, `title`, `type`, `status`.
2. Controlled vocabularies for `type` and `status`.
3. Unique `id` and `slug` across the wiki.
4. Every `[[Wikilink]]` resolves.
5. `reviewed`/`disputed` claims carry evidence referencing a listed source
   (`--strict` makes missing evidence an error).
6. `sha256:` source digests; future `freshness.expires_at`.
7. Redistributable pages declare a license.

---

## Development

```bash
pip install -e ".[dev]"
python3 -m pytest          # 26 tests: yamlio, lint, search (both back-ends), CLI, MCP
make lint                  # validate the sample wiki (strict)
```

CI (`.github/workflows/ci.yml`) runs the tests on Python 3.9/3.11/3.12,
validates the wiki, and proves the toolkit + YAML fallback work with **no**
third-party packages installed.

---

## Design philosophy

> The LLM proposes. Schemas constrain. Evidence grounds. Tests measure.
> Policy gates. Humans authorize high-impact promotion. Git/provenance remembers.

- **Raw evidence is immutable; synthesis is replaceable** — sources are
  content-addressed; pages are projections that can be rebuilt from claims.
- **Review status is data** — machine-readable states, not prose labels.
- **Provenance descends below page level** — evidence attaches to atomic claims.
- **Format interoperability over lock-in** — a rich internal model with tested
  adapters (a natural home for OKF / RO-Crate / DCAT / Croissant exports next).

## Roadmap
Layers from the research baseline not yet implemented here, in priority order:
dependency-aware freshness (source-digest → claim invalidation), first-class
contradiction objects, a knowledge-specific eval suite (citation entailment,
entity resolution, incremental stability), and interoperability exporters
(Google OKF, RO-Crate, DCAT 3, Croissant, SPDX/REUSE).

## License
[MIT](LICENSE).
