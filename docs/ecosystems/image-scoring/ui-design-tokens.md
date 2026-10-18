---
type: Technical Reference
title: Design tokens package (image-scoring-ui)
description: Shared VS Code Dark+ tokens for backend SPA, gallery, and Gradio surfaces.
resource: ecosystems/image-scoring/ui-design-tokens.md
tags: [image-scoring, ui, design-tokens]
timestamp: 2026-09-27T00:00:00Z
okf_version: 0.1
---

# @synthet/image-scoring-design

Repository: [synthet/image-scoring-ui](https://github.com/synthet/image-scoring-ui)

## Canonical artifact

**`src/tokens.json`** — CSS and TypeScript outputs are generated in `dist/` (`npm run build`).

## Consumption

| Consumer | Pattern |
|----------|---------|
| Gallery | `@import` `tokens.css` in CSS Modules |
| Backend SPA | Tailwind v4 `@import` `tailwind-theme.css` |
| Gradio | `gradio-snippet.css` after main UI CSS |
| CI / no sibling | `github:synthet/image-scoring-ui#v1.2.0` (or current tag) |

Local sibling: `"@synthet/image-scoring-design": "file:../image-scoring-ui"` — run `npm run build` in UI repo before `npm install` in consumers.

## Docs

`docs/DESIGN_SYSTEM.md`, `docs/UX_UI_CONSTITUTION.md` on GitHub.
