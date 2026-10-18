---
type: Technical Reference
title: Shared agent infrastructure
description: synthet-code-framework, synthet-llm-wiki, and jev-mcp roles in the Image Scoring workstation.
resource: ecosystems/image-scoring/infrastructure-agents-wiki-jev.md
tags: [image-scoring, framework, llm-wiki, jev]
timestamp: 2026-09-27T00:00:00Z
okf_version: 0.1
---

# Shared infrastructure

## synthet-code-framework

Generic agent SDLC scaffold (commands, skills, `.agent/` governance). **Hub** refreshes via `image-scoring/scripts/framework-adopt.ps1`. **App repos** cherry-pick improvements; Cursor-first sync policy in backend `docs/raw/framework-adoption-port-manifest.md`.

## synthet-llm-wiki

| Surface | Path | Use |
|---------|------|-----|
| OKF docs | `docs/` | Edit markdown + frontmatter; `okf_lint` |
| Product wiki | `.llmwiki/`, `wiki/pages/` | Ingest/compile/review/render only via `llmwiki` CLI or MCP |
| This bundle | `docs/ecosystems/image-scoring/` | Comprehensive Image Scoring family docs |

MCP: **`llmwiki-ro-core`**. Skill: `llm-wiki` in hub and app repos.

Private operator notes: optional git clone `synthet/my-docs` into `wiki/` — see `docs/private-docs.md` in llm-wiki repo.

## jev-mcp

TypeSafe **System One** stdio server. Checkout `D:\Projects\jev-mcp`; token in `jev-mcp/.env` (`JEV_ENV_FILE`). Integrate from hub: `.\scripts\jev-mcp-integrate.ps1`.

## Optional siblings

- **subagent-orchestrator** — external Codex/Gemini review MCP (backend `docs/technical/EXTERNAL_CLI_REVIEWS.md`).

## Cross-links

- [agents-mcp-and-jev.md](agents-mcp-and-jev.md)
- [hub-meta-workspace.md](hub-meta-workspace.md)
