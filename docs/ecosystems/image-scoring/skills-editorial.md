---
type: Guide
title: Image Scoring Skills (editorial prompts)
description: Photo review, carousel curation, and optional ML scores from backend Postgres via MCP.
resource: ecosystems/image-scoring/skills-editorial.md
tags: [image-scoring, skills, prompts, carousel]
timestamp: 2026-09-27T00:00:00Z
okf_version: 0.1
---

# Image Scoring Skills

Repository: [synthet/image-scoring-skills](https://github.com/synthet/image-scoring-skills)

## Role

Prompt-driven assistant for photographers: `/review`, `/score`, `/carousel`, `/folder-score`, Lightroom and species caption flows. **No application runtime** in this repo — persona in `prompts/system.md`.

## ML scores (separate from editorial 1–10)

Normalized **0–1** model scores live in **backend Postgres**. Skills repo can query via MCP when `../image-scoring-pipeline` is a sibling and `.cursor/mcp.json` enables the imgscore stdio or SSE server.

Authority: `docs/image-scoring-db.md`, skill `imgscore-db`.

## Commands index

`docs/commands-and-skills.md`, `AGENTS.md`.

## Cross-links

- [backend-vexlum-scoring.md](backend-vexlum-scoring.md)
- [agents-mcp-and-jev.md](agents-mcp-and-jev.md)
