---
type: Guide
title: MCP and Editor Setup
description: Stdio MCP setup for Claude Code, Cursor, Codex, and thin Gemini CLI compatibility.
resource: mcp-and-editors.md
tags: [docs, mcp, claude, cursor, codex, gemini]
timestamp: 2026-09-07T00:00:00Z
okf_version: 0.1
---

# MCP and editor setup

Install the project first (`pip install -e .` or `uv sync`). Verify with:

```bash
llmwiki mcp --root /absolute/path/to/wiki
```

The default server is read/search oriented. Add `--allow-writes` only for ingestion, compilation,
refresh, rendering, migration, or cache operations. Add `--allow-review` separately for review
state changes. Do not store credentials in project MCP files.

## Checkout-based

Claude Code uses `.mcp.json`; Cursor copies `.cursor/mcp.example.json` to its ignored
`.cursor/mcp.json`; Codex reads `.codex/config.toml` after trust. These project entries invoke
`scripts/run_llmwiki_mcp.py`, whose location determines the repository root, so the server does not
depend on the integration client's working directory. Replace `${workspaceFolder}` with an absolute
checkout path in clients that do not expand it.

Windows installed-command example:

```json
{"command":"llmwiki.exe","args":["--root","D:\\Knowledge\\wiki","mcp"]}
```

Unix installed-command example:

```json
{"command":"llmwiki","args":["--root","/srv/knowledge/wiki","mcp"]}
```

For a write-capable server add `--allow-writes`; for a review-only server add `--allow-review`.
Prefer separate named entries so authority is visible.

## Gemini compatibility

`GEMINI.md` and `.gemini/commands/wiki/*.toml` are thin, manually owned adapters. They call the same
`llmwiki` CLI and do not define another store, schema, or workflow. Claude assets under `.claude/`
are canonical for the framework; Cursor/Codex mirrors are regenerated, while Gemini files are
covered by a contract test.

