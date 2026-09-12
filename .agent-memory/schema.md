# Agent memory schema

## Session log (YAML in `raw-sessions/`)

Each file is named `YYYY-MM-DDTHHMMSSZ.yaml` (UTC).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `timestamp` | string (ISO-8601 UTC) | yes | When the session ended |
| `task_summary` | string | yes | One-line description of work |
| `files_touched` | list of strings | no | Paths inspected or changed |
| `commands_run` | list of strings | no | Shell commands (no secrets) |
| `tests_run` | list of strings | no | Test commands |
| `test_results` | string | no | Pass/fail/skip summary |
| `key_decisions` | list of strings | no | Architectural or approach choices |
| `errors_or_blockers` | list of strings | no | Failures encountered |
| `final_outcome` | string | no | How the session ended |
| `memory_candidates` | list of objects | no | Items for consolidation (see below) |

### `memory_candidates[]`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | yes | Proposed memory summary. Retained as promoted `summary`. |
| `category` | enum | yes | See categories below |
| `confidence` | enum | yes | `low`, `medium`, `high` |
| `id` | string | no | Stable promoted memory id. If omitted, consolidation derives a deterministic `mem-<hash>` id from section + normalized summary. |
| `source_hint` | string | no | Provenance note such as source doc, issue, PR, or session. If omitted during consolidation, the raw session filename is used. |
| `verified_at` | date (`YYYY-MM-DD`) | no | Date a human last verified the fact. Never synthesized during consolidation. |
| `verification_status` | enum | no | `unverified`, `verified`, `failed`, or `needs_review`. Defaults to `unverified`; verification must be explicit. |
| `stale_after` | date (`YYYY-MM-DD`) | no | Date when this item must be re-verified regardless of age threshold. |
| `related_paths` | list of strings | no | Repo paths relevant to the memory. |
| `related_tasks` | list of strings | no | Related task, issue, or PR references. `related_issues` / `related_prs` are accepted aliases and consolidated into this field. |

### Categories

- `stable_fact` — Durable architecture/stack facts
- `user_preference` — Long-lived style or workflow preferences
- `working_rule` — How agents should operate in this repo
- `recurring_issue` — Repeated traps, flaky tests, env problems
- `successful_pattern` — Approaches that worked well
- `open_question` — Unverified assumptions
- `deprecated` — Superseded guidance (audit only)

## Approved memory (`memory.md`)

Markdown with fixed H2 sections (order matters for parsing):

1. `## Stable Project Facts`
2. `## User Preferences`
3. `## Working Rules`
4. `## Recurring Issues`
5. `## Successful Patterns`
6. `## Open Questions`
7. `## Deprecated / Superseded`

Bullet lines use `- ` prefix. Empty section: `- (none yet)`.

Promoted items are stored as structured markdown blocks: the bullet is the human-readable summary,
followed by an indented YAML metadata block. The consolidation engine preserves these fields during
promotion and merges duplicate candidates by keeping one stable id, the highest confidence, the most
recent verification date/status, and the union of provenance/path/task references.

Observation and verification clocks are intentionally separate: `observed_at` is the latest raw
session observation, `last_updated_at` records the last genuinely new observation that changed the
consolidated record, and `verified_at` records only explicit human verification. The
`observation_sessions` list makes replay of the same raw session idempotent.

```markdown
- Sync generated Cursor assets after Claude asset edits. (updated: 2026-07-07)
  id: mem-docs-sync
  summary: Sync generated Cursor assets after Claude asset edits.
  source_hint: .agent/SKILL_CHANGE_AST10_REVIEW.md
  confidence: high
  observation_sessions: [2026-07-07T120000Z.yaml]
  observed_at: 2026-07-07
  last_updated_at: 2026-07-07
  verified_at: 2026-07-07
  verification_status: verified
  stale_after: 2027-01-07
  related_paths:
  - .claude/
  - .cursor/
  related_tasks:
  - PR #123
```

Items may also carry the legacy inline date suffix:

```markdown
- <text> (updated: YYYY-MM-DD)
```

The date is set from the first observation and refreshed only when a previously unconsumed session
confirms the item. Items whose date is older than `staleness_threshold_days` (config, default 180),
or whose explicit `stale_after` date has passed, are flagged in the dream changelog under
`## Stale / needs re-verification` for human review.

### Optional `memory.yaml` representation

Tools may use `.agent-memory/memory.yaml` instead of structured markdown if a consumer needs a pure
data file. It should contain the same section names and item fields:

```yaml
Working Rules:
  - id: mem-docs-sync
    summary: Sync generated Cursor assets after Claude asset edits.
    source_hint: .agent/SKILL_CHANGE_AST10_REVIEW.md
    confidence: high
    verified_at: 2026-07-07
    verification_status: verified
    stale_after: 2027-01-07
    related_paths: [.claude/, .cursor/]
    related_tasks: [PR #123]
```

## Dream proposal (`dreams/*.md`)

YAML front matter between `---` delimiters:

```yaml
generated_at: ISO-8601
source_sessions: [list of raw session filenames]
consumed_sessions: [all raw session filenames represented by this proposal]
item_counts: {section: count}
```

Promotion retains `consumed_sessions` in `memory.md` front matter. Later dream runs skip those raw
sessions by default; `dream.py --replay` explicitly opts into replaying them.

Body uses the same H2 sections and structured item metadata blocks as `memory.md`.

## Changelog (`dreams/*-changelog.md`)

Sections: `## Added`, `## Updated`, `## Removed`, `## Deprecated`, `## Uncertain / needs review`,
`## Stale / needs re-verification`.

Each entry: bullet with text and optional `(from: session-file.yaml)`.
