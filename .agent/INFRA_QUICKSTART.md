# Infra quickstart — LLM Wiki

One page: what to run, what's safe, and what never to touch.

## Purpose

Get an agent productive fast without breaking safety invariants.

## Safe commands (read-only first)

```bash
git status && git log --oneline -n 20      # repo state
python scripts/okf_lint.py --profile project --exclude-prefix archive/ docs   # docs health
python scripts/agent-memory/context.py     # load project memory
python -m pytest                                # tests (see AGENTS.md)
```

## After changing agent assets

```bash
python scripts/sync_assistant_trees.py     # regenerate Cursor and Codex mirrors from .claude/
python scripts/validate_cli_skills.py      # CLI skill structure (when CLI skills changed)
```

## LLM Wiki MCP (default)

- **Server key:** `llmwiki-ro-core` (read/search). Committed in `.mcp.json`, `.cursor/mcp.example.json`, `.codex/config.toml`.
- **Cursor:** copy `.cursor/mcp.example.json` → `.cursor/mcp.json` and reload MCP.
- **Claude Code:** enable `llmwiki-ro-core` from `.mcp.json` in local settings.
- **Codex:** trust the repo so `.codex/config.toml` loads.
- **Skill:** `llm-wiki` — OKF `docs/` vs `.llmwiki/`; see [`docs/mcp-and-editors.md`](../docs/mcp-and-editors.md).
- **Smoke:** `uv run python -m pytest -q tests/test_mcp_sdk.py`

## Optional MCP (fff, Graphify)

- **fff:** Fast indexed repo search — install [fff-mcp](https://github.com/dmtrKovalenko/fff), copy `_examples.proj-ro-fff` from `.cursor/mcp.example.json` into gitignored `.cursor/mcp.json`, reload MCP.
- **Graphify:** Local knowledge graph — `uv tool install graphifyy` (MCP: `graphifyy[mcp]`), run `graphify .` to build `graphify-out/graph.json`, copy `_examples.proj-ro-graphify` into `.cursor/mcp.json`. Do **not** run bare `graphify cursor install` in this scaffold (sync SoT). See [`AGENTS.md`](../AGENTS.md).

## Known pitfalls

- Edit assets under `.claude/` (canonical), not `.cursor/`, `.agents/skills/`, or `.codex/agents/` (generated).
- Memory: never hand-edit `.agent-memory/memory.md`; use log → dream → promote.
- `.agent/scratch/`, `.agent-memory/raw-sessions/`, `.agent-memory/dreams/`, `.agent-runs/` are gitignored.

## Do not

- Do not modify `.git/config` or add git extensions.
- Do not commit secrets (`secrets.json`, `.env`).
- Do not run write-capable MCP tools without an explicit request ([`SAFETY.md`](SAFETY.md)).
