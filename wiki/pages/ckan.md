---
id: entity:ckan
title: CKAN
type: entity
slug: ckan
status: reviewed
aliases: [ckan]
tags: [open-data, catalog, publication]
created: 2026-09-05T00:00:00Z
updated: 2026-09-05T00:00:00Z
sources:
  - id: source:ckan
    uri: https://ckan.org/
    digest: sha256:4444444444444444444444444444444444444444444444444444444444444444
    rights: agpl-3.0
claims:
  - id: claim:ckan-purpose
    text: >-
      CKAN is an open-source data-management system used to publish, share and
      consume datasets through data hubs and portals.
    status: reviewed
    confidence: 0.92
    evidence:
      - source_id: source:ckan
        locator: {type: document}
freshness:
  checked_at: 2026-09-05T00:00:00Z
  stale: false
rights:
  license_expression: AGPL-3.0
  redistribution_allowed: true
---

# CKAN

**CKAN** is the production-grade open-data catalog and portal maintained under
the [[Open Knowledge Foundation]] ecosystem. It serves the catalog and
publication layer of the recommended architecture: after an [[LLM Wiki]] release
bundle is produced, CKAN makes it discoverable and downloadable.

CKAN sits *downstream* of [[Frictionless Data]] validation, not in place of it.
