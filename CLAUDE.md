# LLM Wiki — Local-first evidence-bound LLM Wiki knowledge compiler with CLI and MCP interfaces.

> Seeded from **synthet-code-framework**. Replace this orientation with project specifics, but keep
> the **Backlog**, **Development Guidelines**, and **Documentation** sections — they encode reusable
> contracts. Run `python scripts/sync_assistant_trees.py` after editing `.claude/` assets; it updates
> both Cursor and Codex mirrors.

<!-- Optional: list sibling repos this one coordinates with.
## Related Projects

| Project | Repository | Role |
|---------|------------|------|
| LLM Wiki (this) | https://github.com/synthet/llm-wiki | … |
-->

## Backlog & queue (read this before picking work)

The canonical queue is the configured **backlog provider**, not ad hoc `TODO.md` notes. Generic projects default to Local Markdown; GitHub-hosted projects may use GitHub Issues; GitHub Projects is optional when a board is explicitly configured.

**Mandatory contract for every agent (human or AI). Do all five steps:**

1. **Pick from the ready queue**, sorted by priority. If ready work is empty, ask the maintainer — do not invent work.
2. **Claim** the item: `/task-claim <item-ref>` records ownership in the provider.
3. **Move to in progress** on your first commit.
4. **If blocked**, mark the item blocked and record the blocker + what would unblock it.
5. **Reference the item in the PR** with the provider-specific reference (`Refs <ID>` or `Closes #<N>`).

Do not add tasks to random `TODO.md` files, do not work without a backlog item, and do not skip provider status transitions.
Full contract: [`docs/project/00-backlog-workflow.md`](docs/project/00-backlog-workflow.md) and provider details in [`.agent/backlog/`](.agent/backlog/README.md).

## Architecture

| Module / component | Role |
|--------------------|------|
| `src/llmwiki/store.py` | SQLite schema, migrations, transactions, jobs |
| `src/llmwiki/ingest.py` | bounded file/URL acquisition and text/PDF extraction |
| `src/llmwiki/tree.py` | deterministic local hierarchical document index |
| `src/llmwiki/service.py` | canonical application workflows shared by adapters |
| `src/llmwiki/render.py` | deterministic Markdown projections/conflict detection |
| `src/llmwiki/cli.py`, `mcp_server.py` | CLI and maintained-SDK stdio MCP adapters |

## Key Files

- `pyproject.toml` — Python 3.11+ package/dependency/entry-point contract
- `docs/architecture.md` — product data and service boundaries
- `docs/schema.md` — canonical records, locators, lifecycle, versions
- `docs/security.md` — repository and product threat model

## Commands

```bash
uv sync --extra dev
uv run python -m pytest -q
uv run ruff check .
uv run python -m compileall -q src tests
```

## Testing

Tests live in `tests/`. The default suite is fully offline and includes a real stdio MCP client/server
flow. Remote API and live local-model checks are opt-in and must never be reported as passing unless
explicitly run against an operator-configured endpoint.

Canonical product invariants are in `AGENTS.md`: source bytes/SQLite are truth, generated claims are
candidate until explicit human review, evidence must resolve exactly, reviewed-only is the default,
and provider modes never auto-switch.


## Tool permissions and write access

- **Default read-only mode:** the scaffolded `.claude/settings.json` only allows read-oriented inspection (`git status`, `git diff:*`, `git log:*`) plus `WebSearch`.
- **Local writes are opt-in:** to let an agent stage or commit local changes, copy or merge `.claude/settings.write.example.json` into the active Claude settings for that workspace, preferably enabling only the entries needed for the current task.
- **Remote writes are separate:** GitHub mutations through `gh pr:*`, `gh issue:*`, or `gh project:*` affect shared remote state and may notify people; enable them only after explicit task intent and target verification.
- **External export approval:** exporting code, prompts, logs, or generated artifacts to external services/providers requires explicit approval and a secrets check, even when local writes are already allowed.
- **Bootstrap inheritance:** seeded projects inherit the read-only `.claude/settings.json` so new repos begin with the safer default.

## Development Guidelines

- **No hardcoded paths** — use a config module / base-dir constant.
- **Use the logging facility** — no `print()` in library code.
- **Keep public interfaces stable** — API paths, config keys, shared types, DB column names.
- **Minimal diffs** — prefer targeted edits over rewrites; no drive-by refactors.
- **Secrets** (API keys, tokens) go in `secrets.json` / `.env` (git-ignored), never in committed config.
- **Never modify `.git/config`** — do not set `extensions.worktreeConfig`, change
  `core.repositoryformatversion`, or add git extensions. Third-party tools using embedded git libraries
  choke on non-standard extensions. If a worktree is needed, use a temporary one and clean it up immediately.

## Documentation

Start with [`docs/CANONICAL_SOURCES.md`](docs/CANONICAL_SOURCES.md) (authority map), then
[`docs/WIKI_SCHEMA.md`](docs/WIKI_SCHEMA.md) when adding/moving wiki pages.

- [`AGENTS.md`](AGENTS.md) — MCP config, tool surface, agent contract
- [`docs/ai-workflow/README.md`](docs/ai-workflow/README.md) — agent asset map + SDLC loop
- [`.agent/SAFETY.md`](.agent/SAFETY.md) — safety & hygiene rules
- [`.agent/AGENT_INFRA_INVENTORY.md`](.agent/AGENT_INFRA_INVENTORY.md) — full agent-infra inventory
