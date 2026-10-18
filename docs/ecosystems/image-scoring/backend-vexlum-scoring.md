---
type: Technical Reference
title: Vexlum Scoring (image-scoring-pipeline)
description: Backend pipeline, Postgres, Gradio WebUI, and primary MCP surface is-be-*.
resource: ecosystems/image-scoring/backend-vexlum-scoring.md
tags: [image-scoring, backend, vexlum, postgres]
timestamp: 2026-09-27T00:00:00Z
okf_version: 0.1
---

# Vexlum Scoring — backend

Repository: [synthet/image-scoring-pipeline](https://github.com/synthet/image-scoring-pipeline)

## Role

- Multi-model **quality scoring** (MUSIQ, LIQE, and related models), keyword extraction, RAW support, GPU batch paths.
- **PostgreSQL** is the primary database for Docker and modern deployments (`database.engine`: `postgres` or `api`).
- **Gradio WebUI** default `http://localhost:7860`.
- **MCP** compact server: **`is-be-mcp`** (`search` + `dispatch`); optional live SSE **`is-be-live`** when WebUI runs.

## Operator entry points

| Task | Where |
|------|--------|
| Quick setup | Root `README.md` (Docker / WSL / Windows) |
| Doctor | `python scripts/doctor.py` — see `docs/DIAGNOSTICS.md` |
| Agent contract | `AGENTS.md` |
| Doc hub | `docs/README.md`, `docs/features/implemented/INDEX.md` |

## Default Docker stack

```bash
docker compose up -d --build db webui
```

Postgres on `localhost:5432`; WebUI on `7860`.

## Testing (agents)

Fast subset (see `AGENTS.md`): `pytest -m "not gpu and not db and not ml"`. WSL venv conventions in `.cursor/rules/python-wsl-webapp-env.mdc`.

## Cross-links

- Gallery consumer: [gallery-driftara.md](gallery-driftara.md)
- Eye-quality phase: [model-eye-quality.md](model-eye-quality.md)
- Canonical table: [canonical-sources.md](canonical-sources.md)
