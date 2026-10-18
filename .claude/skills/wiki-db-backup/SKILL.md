---
name: wiki-db-backup
description: Use when the user asks to back up the LLM Wiki SQLite store, repeat a Drive backup, snapshot wiki.db on demand, or copy .llmwiki to external storage before risky work. Runs the compiled harness; does not commit or push.
capability: "On-demand filesystem backup of .llmwiki/wiki.db to a timestamped folder"
side_effect_level: local_write
approval_required: false
requires_tools: "python .claude/skills/wiki-db-backup/scripts/harness.py; optional llmwiki validate"
output_schema: "Harness JSON with backup_dir, copied files, digests, and restore notes"
risk_class: medium
---

# Wiki DB backup (on demand)

Thin bootloader. Copy logic lives in the harness. Treat backups as **sensitive** (sources, claims,
and object bytes may include private documents).

## Invoke

```bash
# Plan only (paths + sizes, no writes)
python .claude/skills/wiki-db-backup/scripts/harness.py --dry-run --json

# Default destination: D:/Goolge Drive or D:/Google Drive when present, else LLMWIKI_DB_BACKUP_ROOT
python .claude/skills/wiki-db-backup/scripts/harness.py --json

# Custom folder (parent must exist or be creatable)
python .claude/skills/wiki-db-backup/scripts/harness.py --dest "D:/Goolge Drive/llm-wiki-backups/synthet-llm-wiki" --json

# Include content-addressed objects/ tree (larger, needed for full filesystem restore)
python .claude/skills/wiki-db-backup/scripts/harness.py --include-objects --json
```

Environment override: `LLMWIKI_DB_BACKUP_ROOT` → base directory (timestamped child folder is still created).

## Agent workflow

1. **Confirm wiki root** — default `discover_root()` from repo cwd; pass `--wiki-root` when ambiguous.
2. **Dry-run** when the user has not confirmed a destination or disk space is uncertain.
3. **Run harness** without `--dry-run`; report `backup_dir`, `files[]`, and `wiki_db_sha256`.
4. **Optional** `uv run llmwiki validate --json` before backup when the store may be inconsistent.
5. **Do not** delete `.llmwiki/` or prune backups unless the user explicitly asks.

## Restore (human)

- **This harness:** stop writers, copy `wiki.db` (+ `-wal`/`-shm` if present) back into `.llmwiki/`;
  restore `objects/` when it was included in the backup.
- **Portable export:** `llmwiki export backup.json` — see [`docs/backup-and-migration.md`](../../../docs/backup-and-migration.md).

## Logging

After a user-requested backup during ingest/consume work, append one line to `docs/log.md` with the
`backup_dir` path (no secrets).
