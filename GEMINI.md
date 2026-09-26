# Gemini CLI compatibility

Gemini support is a thin adapter to the same `llmwiki` CLI/MCP services. It does not own schema,
state transitions, generated pages, or a separate workflow. Follow `AGENTS.md` and the canonical
`.claude/skills/llm-wiki/SKILL.md`; never edit generated `wiki/pages/` or `.llmwiki/` directly.

The `.gemini/commands/wiki/*.toml` commands call the installed `llmwiki` entry point. Keep these
manually owned adapters small. Claude assets remain canonical for generated Cursor/Codex mirrors.

## MCP

When the Gemini CLI supports project MCP, register the same stdio server as other editors:
`llmwiki --root <absolute-wiki-path> mcp`, or from this checkout
`uv run --project . python scripts/run_llmwiki_mcp.py`. Default tools are read/search; ingestion and
review need `--allow-writes` / `--allow-review`. Cross-editor matrix:
[`docs/mcp-and-editors.md`](docs/mcp-and-editors.md).

