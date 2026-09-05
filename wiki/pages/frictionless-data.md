---
id: entity:frictionless
title: Frictionless Data
type: entity
slug: frictionless-data
status: reviewed
aliases: [Frictionless, Frictionless Framework, frictionless-py]
tags: [open-data, validation, data-package]
created: 2026-09-05T00:00:00Z
updated: 2026-09-05T00:00:00Z
sources:
  - id: source:frictionless
    uri: https://framework.frictionlessdata.io/
    digest: sha256:3333333333333333333333333333333333333333333333333333333333333333
    rights: mit
claims:
  - id: claim:frictionless-primitives
    text: >-
      The Frictionless Framework provides Python/CLI primitives to describe,
      extract, validate and transform structured/tabular data.
    status: reviewed
    confidence: 0.9
    evidence:
      - source_id: source:frictionless
        locator: {type: document}
freshness:
  checked_at: 2026-09-05T00:00:00Z
  stale: false
rights:
  license_expression: MIT
  redistribution_allowed: true
---

# Frictionless Data

**Frictionless Data** is an [[Open Knowledge Foundation]] project providing
standards and software to describe, validate, transform, package and publish
data. The Frictionless Framework (`frictionless-py`) implements
`describe` / `extract` / `validate` / `transform`, and Data Package supplies the
lightweight dataset manifest beneath it.

In an [[LLM Wiki]] pipeline, Frictionless is the **quality gate before
ingestion**: raw tabular sources are validated and given a Data Package manifest
before any claim is compiled from them.
