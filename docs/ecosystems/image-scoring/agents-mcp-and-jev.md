---
type: Technical Reference
title: Agents, MCP, and Jev
description: Naming, multi-root MCP keys, harness vs jev-mcp, and llmwiki-ro-core for evidence.
resource: ecosystems/image-scoring/agents-mcp-and-jev.md
tags: [image-scoring, mcp, agents, jev]
timestamp: 2026-09-27T00:00:00Z
okf_version: 0.1
---

# Agents, MCP, and Jev

## MCP naming

| Key | Repo | Role |
|-----|------|------|
| `is-be-mcp` | image-scoring-pipeline | Pipeline / DB / debug dispatch |
| `is-ui-mcp` | image-scoring-gallery | Gallery dispatch |
| `is-be-live` / `is-ui-live` | optional SSE | Running WebUI / Electron dev |
| `llmwiki-ro-core` | synthet-llm-wiki | Evidence search/ask (this bundle ingested) |
| `jev-rw-systemone` | jev-mcp | Ad-hoc System One judgments (paid API) |

**User** `~/.cursor/mcp.json`: cross-repo tools only — not `is-be-*` / `is-ui-*` (see backend `AGENTS.md`).

Build product MCP servers: `npm install && npm run build` in each repo's `mcp-server/`.

## Evidence vs live code

| Need | Use |
|------|-----|
| Reviewed cross-repo facts | `llmwiki-ro-core` + this OKF bundle |
| Live API/schema/ports | Repo `docs/CANONICAL_SOURCES.md` + code |
| Running doctor / DB | `is-be-mcp` or `python scripts/doctor.py` |

## Jev — two layers

| Layer | Location | When |
|-------|----------|------|
| **Harness** (hooks, packs, permissions) | `image-scoring-pipeline/scripts/agent_harness/` | Every Claude Code turn in backend/gallery |
| **MCP** (`jev_choice`, `jev_system_one`, …) | `jev-mcp` | Interactive semantic judgments in chat |

Design note PDF (hub): `Jev Engineering for Coding Agents` — adoption map in hub `docs/guides/JEV_ENGINEERING_ADOPTION.md`. Harness detail: backend `docs/technical/JEV_AGENT_HARNESS.md`.

Hub setup: `.\scripts\jev-mcp-integrate.ps1` from `image-scoring`.

## SDLC (all scaffolded repos)

`/spec → /plan → /implement → /test-and-fix → /pr-ready` — asset map in each repo's `docs/ai-workflow/README.md`.

## Cross-repo contracts

Playbook: hub `.agent/workflows/cross_repo_contract_change.md` (from framework adopt). Owner repo updates contract **first**.
