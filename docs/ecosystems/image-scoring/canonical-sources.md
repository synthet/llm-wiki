---
type: Source-of-Truth Map
title: Image Scoring canonical sources
description: Which repository owns each contract; where agents must look before changing behavior.
resource: ecosystems/image-scoring/canonical-sources.md
tags: [image-scoring, canonical-sources, contracts]
timestamp: 2026-09-27T00:00:00Z
okf_version: 0.1
---

# Canonical sources (ecosystem)

If a fact is not confirmed in the linked file or code, state: **Not confirmed** — do not invent paths,
ports, or column names.

## Meta workspace

| Topic | Authority |
|-------|-----------|
| Sibling layout, manifest, workspace | [image-scoring `repos.manifest.json`](https://github.com/synthet/image-scoring/blob/main/repos.manifest.json), [image-scoring `AGENTS.md`](https://github.com/synthet/image-scoring/blob/main/AGENTS.md) |
| This OKF bundle (comprehensive hub) | `synthet-llm-wiki/docs/ecosystems/image-scoring/` (ingested into LLM Wiki) |

## Backend (Vexlum Scoring)

| Topic | Authority |
|-------|-----------|
| Full authority table | [image-scoring-pipeline `docs/CANONICAL_SOURCES.md`](https://github.com/synthet/image-scoring-pipeline/blob/main/docs/CANONICAL_SOURCES.md) |
| REST / OpenAPI | `docs/technical/API_CONTRACT.md`, `reference/api/openapi.yaml` |
| Config | `docs/technical/CONFIG.md`, `config.example.json`, `modules/config.py` |
| DB schema | `docs/technical/DB_SCHEMA.md`, `migrations/versions/` |
| Pipeline phases | `modules/phases.py`, `docs/technical/PIPELINE_TERMINOLOGY.md` |
| MCP search/dispatch | `docs/technical/MCP_SEARCH_DISPATCH.md`, `mcp/action_registry.json` |
| Jev harness | `docs/technical/JEV_AGENT_HARNESS.md`, `scripts/agent_harness/` |
| Doctor / diagnostics | `docs/DIAGNOSTICS.md`, `scripts/doctor.py` |
| Agent commands | `AGENTS.md`, `.cursor/commands/` |

## Gallery (Driftara)

| Topic | Authority |
|-------|-----------|
| Canonical map | [image-scoring-gallery `docs/CANONICAL_SOURCES.md`](https://github.com/synthet/image-scoring-gallery/blob/main/docs/CANONICAL_SOURCES.md) |
| Development | `docs/DEVELOPMENT.md`, root `README.md` |
| Database modes | `docs/architecture/02-database-design.md` |
| MCP | `mcp-server/`, `.cursor/mcp.example.json` (`is-ui-mcp`) |

## Model (eye-quality)

| Topic | Authority |
|-------|-----------|
| API JSON schema | `docs/technical/API_CONTRACT.md` |
| Backend wiring | `docs/guides/BACKEND_INTEGRATION.md` |
| Pipeline architecture | `docs/architecture/PIPELINE.md` |

## UI package

| Topic | Authority |
|-------|-----------|
| Tokens source | `src/tokens.json` in [image-scoring-ui](https://github.com/synthet/image-scoring-ui) |
| Design system | `docs/DESIGN_SYSTEM.md` |

## Skills (editorial)

| Topic | Authority |
|-------|-----------|
| Commands index | `docs/commands-and-skills.md` |
| ML scores via MCP | `docs/image-scoring-db.md` (sibling backend Postgres) |

## Cross-repo change order

1. Update **owner** repo contract docs and code first (usually backend for API/DB/phases).
2. Regenerate OpenAPI/types when REST changes.
3. Update **consumers** (gallery, UI package version pins).
4. Append `docs/log.md` in each touched repo.
5. Refresh this OKF bundle and re-ingest if ecosystem-facing facts changed.

See [image-scoring-pipeline `docs/technical/AGENT_COORDINATION.md`](https://github.com/synthet/image-scoring-pipeline/blob/main/docs/technical/AGENT_COORDINATION.md).
