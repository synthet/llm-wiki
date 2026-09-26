# MCP wiring and OKF vs product wiki

## Two knowledge surfaces

| Surface | Location | How agents should use it |
|---------|----------|---------------------------|
| **OKF docs bundle** | `docs/` (frontmatter, INDEX, `log.md`) | Edit markdown; run `python scripts/okf_lint.py`; link with relative paths. Not stored in SQLite. |
| **Evidence-bound product wiki** | `.llmwiki/` + generated `wiki/pages/` | **Only** via `llmwiki` CLI or MCP — never hand-edit the DB or rendered pages. |

Use the `llm-wiki` skill (and `/wiki-*` commands) for the product store. Use `task-env-package-tools`
for OKF lint gates; use `/wiki-maintain` after product-store changes that affect docs indexes.

## Default MCP server: `llmwiki-ro-core`

Read/search tools (`search`, `ask`, `list_sources`, tree tools, `validate`, `stats`, …) work out of the
box. Ingestion, compile, render, and review need a separate server entry with `--allow-writes` and/or
`--allow-review` (see [docs/mcp-and-editors.md](../../../../docs/mcp-and-editors.md)).

| Editor | Config file | Notes |
|--------|-------------|--------|
| **Claude Code** | [`.mcp.json`](../../../../.mcp.json) | Enable `llmwiki-ro-core` in local settings; cwd is the repo root. |
| **Cursor** | [`.cursor/mcp.example.json`](../../../../.cursor/mcp.example.json) → gitignored `.cursor/mcp.json` | Uses `${workspaceFolder}`; reload MCP after copy. |
| **Codex** | [`.codex/config.toml`](../../../../.codex/config.toml) | Loaded after the repo is trusted; uses `scripts/run_llmwiki_mcp.py`. |
| **Gemini CLI** | User MCP settings + [`.gemini/commands/wiki/`](../../../../.gemini/commands/wiki/) | Thin CLI adapters; same `llmwiki` binary. Register stdio MCP in Gemini settings if supported. |

Checkout launcher (all editors): `uv run --project <repo> python scripts/run_llmwiki_mcp.py`

Installed launcher (any client):

```bash
llmwiki --root /absolute/wiki/path mcp
```

## Verify

```bash
uv run python -m pytest -q tests/test_mcp_sdk.py
uv run python scripts/ci/check_mcp_config.py
```

Reload the MCP client after config changes.
