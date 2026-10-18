---
type: Documentation Hub
title: Image Scoring ecosystem
description: Cross-repo OKF hub for Vexlum Scoring, Driftara Gallery, eye-quality, design tokens, skills, and agent infrastructure.
resource: ecosystems/image-scoring/README.md
tags: [image-scoring, vexlum, driftara, okf, ecosystem]
timestamp: 2026-09-27T00:00:00Z
okf_version: 0.1
---

# Image Scoring ecosystem (OKF)

**Vexlum Scoring** (`image-scoring-pipeline`) is the AI digital-asset-management and quality pipeline.
**Driftara Gallery** (`image-scoring-gallery`) is the Electron desktop client. Supporting libraries:
**eye-quality** (`image-scoring-model`), **@synthet/image-scoring-design** (`image-scoring-ui`),
editorial prompts (`image-scoring-skills`). The **image-scoring** folder is the meta workspace
(manifest, multi-root Cursor workspace, cross-repo scripts).

This bundle is the **common comprehensive** agent entry point for the family. Repo-specific depth
stays in each repository's `docs/` — use [canonical-sources.md](canonical-sources.md) before
inventing APIs, schema names, or ports.

## Start here

| Audience | Page |
|----------|------|
| New operator | [layout-and-workspace.md](layout-and-workspace.md) |
| Agent / MCP | [agents-mcp-and-jev.md](agents-mcp-and-jev.md) |
| Authority map | [canonical-sources.md](canonical-sources.md) |
| Run / debug | [operations-runbook.md](operations-runbook.md) |

## Products

- [backend-vexlum-scoring.md](backend-vexlum-scoring.md)
- [gallery-driftara.md](gallery-driftara.md)
- [model-eye-quality.md](model-eye-quality.md)
- [ui-design-tokens.md](ui-design-tokens.md)
- [skills-editorial.md](skills-editorial.md)
- [hub-meta-workspace.md](hub-meta-workspace.md)

## Infrastructure

- [infrastructure-agents-wiki-jev.md](infrastructure-agents-wiki-jev.md)

## Evidence wiki

- Ingest: from `synthet-llm-wiki` root, `python scripts/ingest_image_scoring_ecosystem.py`
- Query: MCP `llmwiki-ro-core` (`search` / `ask`) — reviewed claims only unless filtered
- OKF lint: `python scripts/okf_lint.py --profile project docs/ecosystems/image-scoring`

## Navigation

- [INDEX.md](INDEX.md) — flat page list
- Parent: [../INDEX.md](../INDEX.md)
