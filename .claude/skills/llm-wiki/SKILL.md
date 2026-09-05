---
name: llm-wiki
description: >-
  Compile, maintain, validate and search an LLM Wiki — durable interlinked
  Markdown pages with claim-level provenance. Use whenever the user asks to add,
  update, review, search, lint or index knowledge in the wiki/ pages, or to
  answer a question grounded in the wiki.
allowed-tools: Read, Edit, Write, Bash, Glob, Grep
---

# LLM Wiki skill

You maintain a claim-centric knowledge base under `wiki/pages/`. The wiki is a
**projection of claims**: pages render synthesis, but each reviewed factual
statement must be backed by a `claim` with `evidence` tied to a `source`.

## When to use this skill
- Answering a question that the wiki may cover → **search first**, then ground
  the answer in the returned pages (cite the page title/path).
- Adding or updating knowledge → follow the *compile loop* below.
- Reviewing/promoting candidate knowledge → the *review loop*.
- Checking wiki health → `wiki_validate` / `llmwiki lint`, `wiki_stats`.

## Tools
Prefer the `llmwiki` MCP tools (`wiki_search`, `wiki_get_page`, `wiki_validate`,
`wiki_index`, `wiki_stats`, `wiki_backlinks`, `wiki_list_pages`). If MCP is not
available, use the CLI from the repo root:

```bash
PYTHONPATH=src python3 -m llmwiki.cli --root wiki search "<query>" --expand
PYTHONPATH=src python3 -m llmwiki.cli --root wiki get "<title-or-id>"
PYTHONPATH=src python3 -m llmwiki.cli --root wiki lint --strict
PYTHONPATH=src python3 -m llmwiki.cli --root wiki index
```

## The page model (frontmatter)
See `docs/schema.md` for the full spec. Minimum required: `id`, `title`, `type`
(`entity|topic|note|index`), `status`. Reviewed entity/topic pages should carry
`sources` and `claims`, each claim with `evidence`:

```yaml
---
id: entity:example
title: Example
type: entity
slug: example
status: candidate            # candidate until a human reviews
tags: []
sources:
  - id: source:s1
    uri: https://example.com/doc
    digest: sha256:<hex>
    rights: cc-by-4.0
claims:
  - id: claim:example-1
    text: A precise, checkable statement.
    status: candidate
    confidence: 0.8
    evidence:
      - source_id: source:s1
        locator: {type: line-range, start: 10, end: 20}
freshness: {checked_at: 2026-09-05T00:00:00Z, stale: false}
rights: {license_expression: CC-BY-4.0, redistribution_allowed: true}
---
# Example

Body with [[Wikilinks]] to related pages.
```

## Compile loop (add/update knowledge)
1. `wiki_search` for the entity/topic; `wiki_get_page` any near-matches. Reuse an
   existing page rather than creating a duplicate identity.
2. Extract **atomic claims** from the source. For each: write `text`, attach
   `evidence` (source id + locator), set `confidence`, `status: candidate`.
3. If a new claim contradicts an existing one, **do not overwrite**. Keep both,
   set the affected claims/page `status: disputed`, and note the disagreement.
4. Add `[[Wikilinks]]` to related pages; make sure targets exist.
5. `wiki_validate --strict` and fix every error. Then `wiki_index`.
6. Leave synthesis at `candidate` unless the user explicitly approves promotion.

## Review loop (promote candidate → reviewed)
Only when a human asks you to review/approve:
1. Re-read each claim against its cited evidence; confirm the locator supports it.
2. Fix or downgrade unsupported claims (`disputed`/`retracted`).
3. Set `status: reviewed` on the claims and page; record the reviewer/date.
4. `wiki_validate --strict`, then `wiki_index`.

## Guardrails
- Never invent a source or evidence. If you cannot cite it, keep it `candidate`
  and say so.
- Do not delete published knowledge; tombstone with `status: retracted`.
- `id` is canonical; do not rely on filenames for identity.
- Do not commit the generated `wiki/.llmwiki/` index.
