---
id: entity:llm-wiki
title: LLM Wiki
type: entity
slug: llm-wiki
status: reviewed
aliases: [LLM-Wiki, llm-wiki-pattern]
tags: [pattern, knowledge-compilation, rag]
created: 2026-09-05T00:00:00Z
updated: 2026-09-05T00:00:00Z
sources:
  - id: source:karpathy-llm-wiki
    uri: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
    digest: sha256:0000000000000000000000000000000000000000000000000000000000000000
    rights: cc-by-4.0
  - id: source:okf-readme
    uri: https://github.com/GoogleCloudPlatform/open-knowledge-format
    rights: apache-2.0
claims:
  - id: claim:llm-wiki-definition
    text: >-
      An LLM Wiki incrementally compiles source material into durable,
      interlinked Markdown pages that accumulate synthesis, contradictions and
      provenance, rather than re-retrieving raw chunks at query time.
    status: reviewed
    confidence: 0.95
    evidence:
      - source_id: source:karpathy-llm-wiki
        locator: {type: document}
  - id: claim:compile-vs-rag
    text: >-
      The pattern shifts work to "compile time", leaving an accumulating
      knowledge artifact instead of rebuilding context from scratch on every
      query; it complements retrieval rather than replacing it.
    status: reviewed
    confidence: 0.9
    evidence:
      - source_id: source:karpathy-llm-wiki
        locator: {type: document}
freshness:
  checked_at: 2026-09-05T00:00:00Z
  stale: false
rights:
  license_expression: CC-BY-4.0
  redistribution_allowed: true
---

# LLM Wiki

The **LLM Wiki** pattern (popularised by Andrej Karpathy, April 2026) places a
persistent wiki between raw source material and its users. When new information
arrives, the system extracts knowledge, updates entity and topic pages, records
contradictions, and strengthens or challenges earlier synthesis.

The important difference from ordinary query-time RAG is that work happens
incrementally at *compile time*, leaving a durable, auditable artifact. It is
best understood as a **knowledge-compilation architecture**, not a replacement
for search — see [[Claim Ledger]] for the recommended internal model and
[[Provenance and Trust]] for the governance around it.

Google's [[Open Knowledge Format]] formalises this pattern as a portable
Markdown-native exchange format.
