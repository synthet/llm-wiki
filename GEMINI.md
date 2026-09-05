# LLM Wiki — context for Gemini CLI

This repository is an **LLM Wiki**: durable, interlinked Markdown pages compiled
from raw sources with claim-level provenance, plus `llmwiki`, a toolkit to
**index, lint-validate and search** them from a CLI and an MCP server.

## Layout
- `wiki/pages/*.md` — knowledge pages (YAML frontmatter + Markdown).
- `src/llmwiki/` — toolkit (CLI + MCP server).
- `wiki/.llmwiki/` — generated index (do not commit).

## Tools
An MCP server `llmwiki` is configured in `.gemini/settings.json`, exposing
`wiki_search`, `wiki_get_page`, `wiki_validate`, `wiki_index`, `wiki_stats`,
`wiki_backlinks`, `wiki_list_pages`. Custom commands live under
`.gemini/commands/` (`/wiki:search`, `/wiki:lint`, `/wiki:index`, `/wiki:new`).

CLI equivalent (run from the repo root):
```bash
PYTHONPATH=src python3 -m llmwiki.cli --root wiki search "<query>" --expand
PYTHONPATH=src python3 -m llmwiki.cli --root wiki lint --strict
PYTHONPATH=src python3 -m llmwiki.cli --root wiki index
```

## Rules
- Ground domain answers in `wiki_search` results; cite page title/path.
- The wiki is a **projection of claims** — reviewed factual claims must cite
  `evidence` referencing a listed `source`.
- AI-authored content starts as `status: candidate`; only a human promotes to
  `reviewed`. Contradictions are kept and marked `disputed`, never overwritten.
- `id` is canonical identity; filenames/slugs are aliases.
- After editing pages, run `wiki_validate --strict` then `wiki_index`.

See `docs/schema.md` for the full page model.
