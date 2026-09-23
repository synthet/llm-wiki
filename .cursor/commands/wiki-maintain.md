---
capability: "llm-wiki post-change docs and store maintenance"
side_effect_level: local_write
approval_required: false
requires_tools: "llmwiki CLI; docs INDEX/README/log edits; optional python scripts/okf_lint.py / wiki_lint.py"
output_schema: "Maintenance report with validate/render/lint results and log path"
risk_class: medium
---

> **Cursor:** Same intent as Claude `/wiki-maintain`. When customizing, keep in sync with `.cursor/commands/wiki-maintain.md`.

# /wiki-maintain — After ingest/compile (or "update llm wiki")

Close the loop after product-wiki writes or when the user asks to maintain docs/index/log.
Does **not** invent new claims or grant review. Pair with `/wiki-ingest` for new evidence and
`/wiki-lint` for deeper structural audits.

Load the `llm-wiki` skill first. Read [`docs/WIKI_SCHEMA.md`](../../docs/WIKI_SCHEMA.md) before
large `docs/` edits.

## When to run

- User says "update llm wiki", "maintain wiki", "refresh index/docs/log", or similar.
- Immediately after ingest + compile (+ optional render) in the same session.
- After adding/renaming living pages under `docs/` or handwritten notes under `wiki/notes/`.

## Steps

1. **Confirm write path.** Prefer `uv run llmwiki ...` (or MCP with `--allow-writes`). If MCP is
   read-only, say so and use the CLI; do not edit `.llmwiki/wiki.db` or `wiki/pages/*.md` by hand.
2. **Validate:** `uv run llmwiki validate --json` — stop on `ok: false`.
3. **Render:** If claims were added or claim state changed,
   `uv run llmwiki render --include-unreviewed --json` when the store is mostly candidate (this
   repo's current convention). Use default reviewed-only render only when the user wants
   reviewed-only pages. Stop on a render conflict; do not overwrite manual page edits.
4. **Handwritten notes hub:** If `wiki/notes/` gained or lost notes, update
   [`wiki/notes/README.md`](../../wiki/notes/README.md) with a short dated index. Notes are not
   canonical until ingested.
5. **Living docs index:** If `docs/` pages were added/renamed/removed, update the nearest
   `INDEX.md`, and when relevant [`docs/INDEX.md`](../../docs/INDEX.md) and
   [`docs/README.md`](../../docs/README.md).
6. **Activity log:** Append one line under the current month in [`docs/log.md`](../../docs/log.md):
   `- YYYY-MM-DD: <verb> — <details and paths>`
   Verbs: `ingested`, `created`, `updated`, `lint-fixed`, `reorganized`, `maintained`.
7. **Quick docs lint (default):**
   `python scripts/okf_lint.py --profile project --exclude-prefix archive/`
   Optionally `python scripts/wiki_lint.py --exclude-prefix archive/`. Fix broken index entries and
   newly introduced broken links; ask before large taxonomy rewrites.
8. **Report open review work.** List any known bad evidence bounds or claims that need
   `llmwiki review retract ... --reviewer <human>` — never invent a reviewer identity. Point at
   `/wiki-review`.

## Done when

- `validate` is clean.
- Render completed or correctly reported unchanged / conflict.
- INDEX/README/notes hub and `docs/log.md` match the change set.
- User sees a short report: what changed, what stayed candidate, what needs human review.

## Out of scope

- Approving/rejecting/retracting claims without an explicit human reviewer identity (`/wiki-review`).
- Editing generated `wiki/pages/` or SQLite directly.
- Full content staleness / contradiction audits (use `/wiki-lint full`).
