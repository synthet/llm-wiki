---
type: Runbook
title: Image Scoring operations runbook
description: Layout verify, backend doctor, gallery doctor, Docker, and wiki ingest refresh.
resource: ecosystems/image-scoring/operations-runbook.md
tags: [image-scoring, runbook, operations]
timestamp: 2026-09-27T00:00:00Z
okf_version: 0.1
---

# Operations runbook

## 1. Verify workstation layout

```powershell
cd D:\Projects\image-scoring
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
cd D:\Projects\image-scoring
.\scripts\git-status-all.ps1
```

## Config overrides

Per-repo `environment.json` (gitignored) overrides `config.json` for machine paths, ports, and URLs.
