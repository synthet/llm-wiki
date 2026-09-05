---
id: topic:claim-ledger
title: Claim Ledger
type: topic
slug: claim-ledger
status: reviewed
aliases: [claim ledger, canonical claim ledger, claim-centric model]
tags: [architecture, provenance, design]
created: 2026-09-05T00:00:00Z
updated: 2026-09-05T00:00:00Z
sources:
  - id: source:deep-research
    uri: internal://deep-research-report
    digest: sha256:5555555555555555555555555555555555555555555555555555555555555555
    rights: internal
claims:
  - id: claim:page-is-projection
    text: >-
      The authoritative unit should be a versioned claim with source evidence,
      generator identity, timestamps, review state, rights and invalidation
      dependencies; Markdown pages are rendered projections of this claim graph.
    status: reviewed
    confidence: 0.88
    evidence:
      - source_id: source:deep-research
        locator: {type: section, ref: high-priority-improvement-canonical-claim-ledger}
  - id: claim:stable-identity
    text: >-
      Every source, entity, claim and artifact needs an opaque stable id;
      human-readable slugs are aliases, not identities, so renames, Unicode and
      filename collisions do not corrupt references.
    status: reviewed
    confidence: 0.86
    evidence:
      - source_id: source:deep-research
        locator: {type: section, ref: stable-identity}
freshness:
  checked_at: 2026-09-05T00:00:00Z
  stale: false
rights:
  license_expression: internal
  redistribution_allowed: false
---

# Claim Ledger

The most consequential improvement over "Markdown files maintained by an LLM"
is to treat the wiki as **an auditable knowledge compiler whose Markdown is one
output**. The canonical unit is a *claim*, not a page.

A recommended canonical claim record carries: subject, predicate/text, review
`status`, provenance (source id, revision, locator, extractor), trust
(confidence, reviewer), freshness (checked/expires) and rights.

Pages — like this one — are deterministic renderings of the underlying claims.
This is why `llmwiki lint` checks that reviewed claims carry evidence and that
evidence references a listed source. See [[Provenance and Trust]] for the review
lifecycle and [[LLM Wiki]] for the surrounding pattern.
