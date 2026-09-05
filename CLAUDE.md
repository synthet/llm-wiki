# LLM Wiki — project rules for Claude Code

This repository is an **LLM Wiki**: durable, interlinked Markdown pages compiled
from raw sources, with claim-level provenance. It ships `llmwiki`, a toolkit to
**index, lint-validate and search** the wiki from both a CLI and an MCP server.

## Layout
- `wiki/pages/*.md` — the knowledge pages (YAML frontmatter + Markdown body).
- `src/llmwiki/` — the toolkit (CLI `llmwiki`, MCP server `llmwiki-mcp`).
- `wiki/.llmwiki/` — generated search index (gitignored).

## Tools you should use
An MCP server named `llmwiki` is configured in `.mcp.json`. Prefer its tools:
- `wiki_search` — find relevant pages before answering; ground answers in them.
- `wiki_get_page` — read a page's claims, sources and links.
- `wiki_validate` — lint the wiki; **must pass before you commit**.
- `wiki_index` — rebuild the index after editing pages.
- `wiki_stats`, `wiki_backlinks`, `wiki_list_pages` — inspect the graph/health.

Equivalent CLI (run from the repo root):
```
PYTHONPATH=src python3 -m llmwiki.cli --root wiki search "<query>"
PYTHONPATH=src python3 -m llmwiki.cli --root wiki lint --strict
PYTHONPATH=src python3 -m llmwiki.cli --root wiki index
```
(Or just `llmwiki ...` when the package is installed.)

## Invariants — do not violate
1. The wiki is a **projection of claims**; every reviewed factual claim carries
   `evidence` referencing a listed `source`.
2. `status` is machine-readable data. New/LLM-authored content starts as
   `candidate`; only a human/policy gate promotes it to `reviewed`.
3. Never silently overwrite a contradiction — keep competing claims and set
   status `disputed`.
4. Filenames/slugs are **aliases, not identity**. The `id` field is canonical.
5. Wikilinks `[[Target]]` must resolve. Run `wiki_validate` to check.
6. Record source `uri` and a `sha256:` `digest`; declare `rights`.

## Workflow for editing knowledge
1. `wiki_search` / `wiki_get_page` to see what already exists.
2. Edit or add pages under `wiki/pages/` (see `docs/schema.md` for the model, or
   `llmwiki new "Title"` for a template).
3. `wiki_validate --strict` — fix every error.
4. `wiki_index` so search reflects the change.
5. Leave new synthesis at `status: candidate` unless a human approves it.

## Commit conventions
Run the tests (`python3 -m pytest`) and `wiki_validate` before committing.
Do not commit `wiki/.llmwiki/`.
