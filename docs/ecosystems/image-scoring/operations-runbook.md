---
type: Runbook
title: Image Scoring operations runbook
description: Layout verify, backend doctor, gallery doctor, Docker, and wiki ingest refresh.
resource: ecosystems/image-scoring/operations-runbook.md
tags: [image-scoring, runbook, operations]
timestamp: 2026-11-05T00:00:00Z
okf_version: 0.1
---

# Operations runbook

## 1. Verify workstation layout

```powershell
cd <projects-root>\image-scoring
.\scripts\layout-doctor.ps1
```

## 2. Backend health

```bash
cd image-scoring-pipeline
python scripts/doctor.py
```

See `docs/DIAGNOSTICS.md` for debug bundles.

## 3. Gallery health

```bash
cd image-scoring-gallery
npm run doctor
```

## 4. Docker (backend)

```bash
docker compose up -d --build db webui
docker compose ps
```

## 5. Refresh LLM Wiki evidence (this bundle)

From `synthet-llm-wiki` checkout:

```bash
python scripts/ingest_image_scoring_ecosystem.py
llmwiki validate
llmwiki render
```

Human-review new **candidate** claims before relying on them in `ask` (default reviewed-only).

## 6. Git status across siblings

```powershell
cd <projects-root>\image-scoring
.\scripts\git-status-all.ps1
```

## 7. Update a remote GPU runner

Full procedure: [Remote GPU runner](https://github.com/synthet/image-scoring-pipeline/blob/master/docs/guides/REMOTE_GPU_RUNNER.md), section "Update a runner".

- Host and runner must share `API_VERSION`. On a mismatch every remote phase fails and fallback does not apply, so update them together.
- Every compose command that reads `docker-compose.gpu-runner.yml` needs `GPU_RUNNER_TOKEN`, including `build`.
- Verify with `GpuRunnerClient.check_phase(phase)` from the host. `ready_client()` can pass through the embedded backend without contacting the runner.
- `check_phase` does not cover model weights, so score one small folder after an update.

## Config overrides

Per-repo `environment.json` (gitignored) overrides `config.json` for machine paths, ports, and URLs.
