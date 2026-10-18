---
type: Technical Reference
title: Driftara Gallery (image-scoring-gallery)
description: Electron + React desktop gallery; MCP is-ui-*; Postgres or API SQL mode.
resource: ecosystems/image-scoring/gallery-driftara.md
tags: [image-scoring, gallery, driftara, electron]
timestamp: 2026-09-27T00:00:00Z
okf_version: 0.1
---

# Driftara Gallery — desktop app

Repository: [synthet/image-scoring-gallery](https://github.com/synthet/image-scoring-gallery)

## Role

High-performance browsing and filtering for libraries scored by Vexlum Scoring. Connects to **PostgreSQL** locally and/or SQL via the **backend API** (`database.engine` in `config.json`).

## MCP

- **`is-ui-mcp`** — same search/dispatch pattern as backend; build `mcp-server` before enabling.
- Optional **`is-ui-live`** when Electron dev server exposes MCP SSE (port documented in backend/gallery AGENTS).

## Development

```bash
npm install
npm run dev
```

Repo doctor: `npm run doctor`. See `docs/DEVELOPMENT.md`.

## Layout

Keep **image-scoring-gallery** sibling to **image-scoring-pipeline** for default API port discovery unless config overrides.

## Agent tree

**Cursor-first** (`.cursor/` canonical → `.claude/` sync). See framework port manifest in backend `docs/raw/framework-adoption-port-manifest.md`.

## Cross-links

- Backend: [backend-vexlum-scoring.md](backend-vexlum-scoring.md)
- Design tokens: [ui-design-tokens.md](ui-design-tokens.md)
