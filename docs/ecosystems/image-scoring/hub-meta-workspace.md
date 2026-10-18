---
type: Technical Reference
title: image-scoring meta hub
description: Umbrella repo — manifest, workspace, framework adopt, cross-repo scripts; no product runtime.
resource: ecosystems/image-scoring/hub-meta-workspace.md
tags: [image-scoring, hub, meta]
timestamp: 2026-09-27T00:00:00Z
okf_version: 0.1
---

# Meta hub (`image-scoring`)

Repository: [synthet/image-scoring](https://github.com/synthet/image-scoring) (umbrella; may be local-only until published)

## What lives here

| Asset | Purpose |
|-------|---------|
| `repos.manifest.json` | Sibling paths, clone URLs, infrastructure (llm-wiki, jev-mcp, framework) |
| `image-scoring.code-workspace` | Multi-root Cursor workspace |
| `scripts/layout-doctor.ps1` | Verify siblings exist |
| `scripts/clone-siblings.ps1` | Clone product + infrastructure repos |
| `scripts/framework-adopt.ps1` | Merge synthet-code-framework agent scaffold |
| `scripts/jev-mcp-integrate.ps1` | Wire jev-mcp MCP + skill |
| `docs/ECOSYSTEM.md`, `docs/guides/*` | Hub-local OKF (also summarized in this LLM Wiki bundle) |

## Agent source of truth

- Hub uses **framework default**: `.claude/` canonical → `.cursor/` via `sync_assistant_trees.py`.
- App repos use **Cursor-first** forks — do not blindly merge framework into backend/gallery.

## Rule

Implement product features in the **owning sibling**; change the hub for manifest, workspace, ecosystem docs, and shared agent wiring only.

## Cross-links

- [layout-and-workspace.md](layout-and-workspace.md)
- [infrastructure-agents-wiki-jev.md](infrastructure-agents-wiki-jev.md)
