---
id: entity:google-okf
title: Open Knowledge Format
type: entity
slug: open-knowledge-format
status: reviewed
aliases: [OKF, Google OKF, open-knowledge-format]
tags: [format, google, interoperability]
created: 2026-09-05T00:00:00Z
updated: 2026-09-05T00:00:00Z
sources:
  - id: source:okf-repo
    uri: https://github.com/GoogleCloudPlatform/open-knowledge-format
    digest: sha256:1111111111111111111111111111111111111111111111111111111111111111
    rights: apache-2.0
claims:
  - id: claim:okf-is-format-not-platform
    text: >-
      Google's Open Knowledge Format (OKF) is an open specification that
      formalises the LLM-wiki pattern as portable Markdown plus structured
      metadata, emphasising a format over a platform and producer/consumer
      independence.
    status: reviewed
    confidence: 0.9
    evidence:
      - source_id: source:okf-repo
        locator: {type: document}
  - id: claim:okf-not-okfn
    text: >-
      Google OKF is not an Open Knowledge Foundation project; the two are
      unrelated organisations despite the abbreviation collision.
    status: reviewed
    confidence: 0.92
    evidence:
      - source_id: source:okf-repo
        locator: {type: document}
  - id: claim:okf-v02-provenance
    text: >-
      OKF v0.2 adds stronger provenance, trust, freshness, lifecycle and
      attestation concepts.
    status: reviewed
    confidence: 0.85
    evidence:
      - source_id: source:okf-repo
        locator: {type: section, ref: v0.2}
freshness:
  checked_at: 2026-09-05T00:00:00Z
  stale: false
rights:
  license_expression: Apache-2.0
  redistribution_allowed: true
---

# Open Knowledge Format

**Open Knowledge Format (OKF)** is a Google specification, announced June 2026,
that formalises the [[LLM Wiki]] pattern into portable Markdown files with YAML
frontmatter and minimal conventions. It is designed as a *format*, not a
platform, keeping knowledge producers and consumers independent.

> Terminology: **Google OKF** (Open Knowledge Format) is distinct from
> **OKFN** ([[Open Knowledge Foundation]]). They are unrelated projects.

Because OKF gives Markdown-native knowledge a neutral wire format, an LLM Wiki
implementation should keep a richer internal model (see [[Claim Ledger]]) and
provide deterministic import/export to OKF rather than adopting it as internal
storage.
