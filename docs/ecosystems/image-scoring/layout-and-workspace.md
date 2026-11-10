---
type: Guide
title: Layout and multi-root workspace
description: Sibling directory layout and image-scoring.code-workspace folder names for MCP.
resource: ecosystems/image-scoring/layout-and-workspace.md
tags: [image-scoring, layout, workspace]
timestamp: 2026-09-27T00:00:00Z
okf_version: 0.1
---

# Layout and workspace

## Sibling directories (this workstation)

```text
<projects-root>\image-scoring              # meta hub
<projects-root>\image-scoring-pipeline        # Vexlum Scoring
<projects-root>\image-scoring-gallery        # Driftara Gallery
<projects-root>\image-scoring-model          # eye-quality
<projects-root>\image-scoring-ui             # design tokens npm package
<projects-root>\image-scoring-skills         # editorial / carousel prompts
<projects-root>\synthet-llm-wiki             # evidence wiki product + this OKF bundle
<projects-root>\jev-mcp                    # TypeSafe Jev MCP
<projects-root>\synthet-code-framework       # generic agent scaffold (upstream)
```

Machine-readable manifest: hub [`repos.manifest.json`](https://github.com/synthet/image-scoring/blob/main/repos.manifest.json).

## Why siblings matter

- **Gallery** discovers backend WebUI port via sibling `webui.lock` unless `api.url` / `api.port` is set in gallery `config.json` / `environment.json`.
- **Skills** MCP launchers assume `../image-scoring-pipeline`.
- **UI package** local dev: `file:../image-scoring-ui` in backend/gallery `package.json`.

## Cursor / VS Code

Open **`image-scoring/image-scoring.code-workspace`**. Folder **names** must match MCP templates:

- `${workspaceFolder:image-scoring-pipeline}`
- `${workspaceFolder:image-scoring-gallery}`
- `${workspaceFolder:synthet-llm-wiki}`
- `${workspaceFolder:jev-mcp}`

Verify: `.\scripts\layout-doctor.ps1` from the hub root.

## Clone missing repos

```powershell
cd <projects-root>\image-scoring
.\scripts\clone-siblings.ps1
```

Infrastructure entries (llm-wiki, jev-mcp) are included when `clone` URLs exist in the manifest.
