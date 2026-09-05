---
id: topic:provenance-and-trust
title: Provenance and Trust
type: topic
slug: provenance-and-trust
status: candidate
aliases: [provenance, trust, review states]
tags: [governance, provenance, freshness]
created: 2026-09-05T00:00:00Z
updated: 2026-09-05T00:00:00Z
sources:
  - id: source:deep-research
    uri: internal://deep-research-report
    digest: sha256:5555555555555555555555555555555555555555555555555555555555555555
    rights: internal
claims:
  - id: claim:review-status-is-data
    text: >-
      Review status (candidate, reviewed, disputed, stale, superseded,
      retracted) should be machine-readable state with explicit transitions,
      not labels casually inserted into prose.
    status: candidate
    confidence: 0.8
    evidence:
      - source_id: source:deep-research
        locator: {type: section, ref: review-status-is-data}
  - id: claim:dependency-freshness
    text: >-
      Source changes should invalidate dependent claims via a dependency graph,
      so a freshly rendered page cannot contain individually stale claims.
    status: candidate
    confidence: 0.78
    evidence:
      - source_id: source:deep-research
        locator: {type: section, ref: dependency-aware-freshness}
freshness:
  checked_at: 2026-09-05T00:00:00Z
  stale: false
rights:
  license_expression: internal
  redistribution_allowed: false
---

# Provenance and Trust

Trust infrastructure is the biggest improvement opportunity for LLM Wiki
implementations. The governance principle:

> LLMs may **propose** knowledge; automated checks may **validate** structure;
> accountable humans or explicitly configured policy gates **authorize**
> promotion.

Review states are first-class data:

| state | meaning |
|---|---|
| `candidate` | LLM-generated, not yet reviewed (the default) |
| `reviewed` | approved by a human/policy gate |
| `disputed` | competing claims retained, not silently overwritten |
| `stale` | a dependent source changed |
| `superseded` | replaced by a newer claim, kept for audit |
| `retracted` | withdrawn, tombstoned rather than deleted |

This page is intentionally left at `candidate` status to demonstrate how
`llmwiki` distinguishes reviewed from unreviewed knowledge. See
[[Claim Ledger]] for the underlying record and [[LLM Wiki]] for context.
