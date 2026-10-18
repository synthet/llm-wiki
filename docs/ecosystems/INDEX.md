---
type: Documentation Index
title: Ecosystem documentation index
description: OKF bundles for multi-repo product families ingested into the evidence wiki.
resource: ecosystems/INDEX.md
tags: [docs, ecosystems, index, okf]
timestamp: 2026-09-27T00:00:00Z
okf_version: 0.1
---

# Ecosystem OKF bundles

Curated **Open Knowledge Format** documentation for sibling-repo families. These pages live in
`docs/ecosystems/<name>/`, pass `okf_lint`, and are ingested into `.llmwiki` for `llmwiki-ro-core`
search/ask (review workflow applies to compiled claims).

| Bundle | Hub | Ingest |
|--------|-----|--------|
| [Image Scoring / Vexlum](image-scoring/README.md) | [image-scoring](https://github.com/synthet/image-scoring) meta workspace | `python scripts/ingest_image_scoring_ecosystem.py` |

Add a new ecosystem by copying the folder pattern: `README.md`, `INDEX.md`, `canonical-sources.md`,
product pages, then register here and in [../INDEX.md](../INDEX.md).
