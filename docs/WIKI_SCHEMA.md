---
type: Documentation Schema
title: Wiki Schema
description: Documentation structure, naming, link, metadata, and maintenance conventions.
resource: WIKI_SCHEMA.md
tags: [docs, schema, okf, maintenance]
timestamp: 2026-09-20T00:00:00Z
okf_version: 0.1
---

# Wiki schema — `docs/` and product wiki

This repository keeps `docs/` as an LLM-maintained OKF wiki (indexes, contracts, activity log) and a
separate **product** LLM Wiki under `wiki/` + `.llmwiki/` (evidence-bound claims).

## OKF alignment

`docs/` is maintained as an [Open Knowledge Format adoption bundle](OKF_ADOPTION.md): markdown files with YAML frontmatter, stable relative paths as concept identities, relative markdown links as the knowledge graph, folder `INDEX.md` hubs, and append-only `log.md` history.

New living pages and materially edited living pages should include YAML frontmatter with at least `type`; recommended fields are `title`, `description`, `resource`, `tags`, `timestamp`, and `okf_version`. See [OKF_ADOPTION.md](OKF_ADOPTION.md) for the local type vocabulary and migration policy.

## Layout in this checkout

| Path | Purpose |
|------|---------|
| [`INDEX.md`](INDEX.md), [`README.md`](README.md) | Docs hubs |
| Root `docs/*.md` | Product and governance living pages (thin entry points) |
| [`ai-workflow/`](ai-workflow/) | Agent asset map and SDLC loop |
| [`project/`](project/) | Backlog workflow and governance |
| [`examples/`](examples/) | Example snippets |
| [`log.md`](log.md) | Append-only activity log |
| [`../wiki/`](../wiki/) | Nested private repo (`synthet/my-docs`); see [private-docs.md](private-docs.md) |
| `../wiki/notes/` | Handwritten sources (private remote; ingest before treating as canonical) |
| `../wiki/pages/` | Generated projections only (`llmwiki render`; local) |

Do not invent empty taxonomy folders (for example `architecture/`, `guides/`) unless you also create
them with an `INDEX.md` hub. Prefer root living pages or an existing folder.

## Naming

- **New docs pages:** prefer `kebab-case.md`.
- **Snapshot notes:** include a date (`topic-YYYY-MM-DD.md`), especially under `wiki/notes/`.
- **Generated pages:** do not rename by hand; change entities via compile/review then re-render.

## Links

- Use **relative** links from the page you are editing.
- Prefer linking to **[`CANONICAL_SOURCES.md`](CANONICAL_SOURCES.md)** from agent-oriented prose when pointing at contracts.
- **Cross-repo:** use full GitHub URLs to a sibling repo when the canonical doc lives there.

## Indexes and activity log

After adding, renaming, or removing pages:

1. Update the nearest folder `INDEX.md` and, when relevant, [`INDEX.md`](INDEX.md) and [`README.md`](README.md).
2. If `wiki/notes/` changed, update [`../wiki/notes/README.md`](../wiki/notes/README.md).
3. Append a line to [`log.md`](log.md) under the current month heading using:
   `- YYYY-MM-DD: <verb> — <details and paths>`
   Verbs: `ingested`, `created`, `updated`, `lint-fixed`, `filed-back`, `reorganized`, `maintained`.

## Slash commands

Project commands under `.cursor/commands/` and `.claude/commands/`:

| Command | Role |
|---------|------|
| `/wiki-ingest` | Ingest one source into the product wiki |
| `/wiki-maintain` | Validate, render, refresh INDEX/README/notes hub, append log |
| `/wiki-lint` | Structural (or full) docs health check |
| `/wiki-query` | Answer from reviewed claims |
| `/wiki-review` | Human approve/reject/retract |

Read this file before large wiki or docs edits. Prefer `/wiki-maintain` after ingest/compile or when
the user asks to "update llm wiki".
