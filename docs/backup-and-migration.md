---
type: Guide
title: Backup, Restore, and Markdown Migration
description: Versioned JSON backup/restore and patch-era Markdown migration procedures.
resource: backup-and-migration.md
tags: [docs, backup, migration, restore]
timestamp: 2026-09-07T00:00:00Z
okf_version: 0.1
---

# Backup, restore, and migration

## Versioned backup

```bash
llmwiki export backup.json --root /absolute/wiki
```

The deterministic JSON contains format/schema versions, canonical table rows, and base64-encoded
immutable source objects verified against their SHA-256. Keep the file in protected local storage;
it can contain the complete source corpus.

Restore only into an initialized, empty canonical store:

```bash
llmwiki init --root /absolute/restored-wiki
llmwiki import backup.json --root /absolute/restored-wiki
llmwiki validate --root /absolute/restored-wiki
llmwiki render --root /absolute/restored-wiki
```

The importer rejects an unknown version, malformed row/object, digest mismatch, or non-empty store.
Generated pages and FTS caches are rebuilt rather than treated as backup authority.

For a direct filesystem snapshot, stop all writers and copy `.llmwiki/wiki.db` (including WAL/SHM
files if present) plus `.llmwiki/objects/`. The versioned JSON route is preferred for portability.

## Patch-era Markdown

```bash
llmwiki import /path/to/old/wiki/pages --format markdown --root /absolute/wiki
```

Original files are read but never moved or modified. Valid UUID identities are retained when they
do not collide. Titles become entity aliases. Factual material without a verifiable immutable
revision and exact locator is imported as `candidate` with no fabricated digest/evidence and cannot
be approved until evidence is attached through a new compilation result.

