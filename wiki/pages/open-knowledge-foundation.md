---
id: entity:okfn
title: Open Knowledge Foundation
type: entity
slug: open-knowledge-foundation
status: reviewed
aliases: [OKFN, Open Knowledge]
tags: [organisation, open-data]
created: 2026-09-05T00:00:00Z
updated: 2026-09-05T00:00:00Z
sources:
  - id: source:okfn-tools
    uri: https://okfn.org/en/what-we-do/tools/
    digest: sha256:2222222222222222222222222222222222222222222222222222222222222222
    rights: cc-by-4.0
claims:
  - id: claim:okfn-stack
    text: >-
      The Open Knowledge Foundation (OKFN) maintains open-data infrastructure
      and policy including CKAN, Frictionless, the Open Data Editor, the Open
      Definition and Open Data Commons licenses.
    status: reviewed
    confidence: 0.93
    evidence:
      - source_id: source:okfn-tools
        locator: {type: document}
freshness:
  checked_at: 2026-09-05T00:00:00Z
  stale: false
rights:
  license_expression: CC-BY-4.0
  redistribution_allowed: true
---

# Open Knowledge Foundation

The **Open Knowledge Foundation (OKFN)** supplies mature infrastructure and
policy for open-data publishing. Its tooling ecosystem includes
[[Frictionless Data]], [[CKAN]], the Open Data Editor, the Open Definition and
the Open Data Commons licenses.

> Not to be confused with Google's [[Open Knowledge Format]] (OKF).

In the recommended architecture, OKFN tools sit around the edges of an
[[LLM Wiki]]: Frictionless validates source data before ingestion, and CKAN
publishes the resulting knowledge bundles.
