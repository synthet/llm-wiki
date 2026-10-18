---
type: Technical Reference
title: eye-quality (image-scoring-model)
description: Wildlife eye pose and eye-focus scoring library; Hugging Face weights; backend phase integration.
resource: ecosystems/image-scoring/model-eye-quality.md
tags: [image-scoring, model, eye-quality, wildlife]
timestamp: 2026-09-27T00:00:00Z
okf_version: 0.1
---

# eye-quality — model repo

Repository: [synthet/image-scoring-model](https://github.com/synthet/image-scoring-model)

## Role

YOLO pose + heuristics for **eye localization** and **stack-relative eye-focus scoring** (wildlife / birds).

## Install (backend environment)

```bash
pip install -e /path/to/image-scoring-model
```

Weights: [synthet/eye-pose-v0](https://huggingface.co/synthet/eye-pose-v0) → `models/eye_pose_v0.pt`.

## CLI

```bash
python -m eye_quality score path/to/image.jpg
eye-quality batch manifest.jsonl --output results.jsonl
```

## Backend integration

Phase `eye_quality` (when wired): runner contract mirrors other phase runners — see `docs/guides/BACKEND_INTEGRATION.md` in the model repo and backend `modules/phases.py`.

## Cross-links

- [canonical-sources.md](canonical-sources.md)
- [backend-vexlum-scoring.md](backend-vexlum-scoring.md)
