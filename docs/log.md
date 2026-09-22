# Wiki activity log

Append-only. One line per wiki restructure, newest under the current month.
Format: `- YYYY-MM-DD: <verb> — <details and paths>` (verbs: `created`, `updated`, `ingested`,
`lint-fixed`, `reorganized`).

## 2026-09

- 2026-09-21: reorganized — private knowledge remote [synthet/my-docs](https://github.com/synthet/my-docs) is now checked out as `wiki/` (no nested `my-docs/` folder); parent gitignores `wiki/`; public `docs/private-docs.md` updated with clone instructions.
- 2026-09-20: maintained — docs INDEX/README already pointed at `private-docs.md`; fixed `WIKI_SCHEMA.md` folder taxonomy to match this checkout (cleared OKF broken-folder warnings); indexed `wiki/notes/README.md`; added `/wiki-maintain` and enriched `llm-wiki` skill with post-ingest evidence/locator and candidate-retract guardrails.
- 2026-09-20: ingested — photo burst eye-sharpness culling notes (`wiki/notes/photo-burst-eye-sharpness-culling-2026-09-20.md`); compiled 32 candidate claims into entities `Vexlum image scoring database`, `Vexlum image quality models`, `Nikon NEF embedded preview extraction`, `Photo burst eye-sharpness culling`, and `OpenCV sharpness measurement pitfalls`; validated and rendered with `--include-unreviewed`. Three claims still carry loosely-bounded evidence quotes and need retract-and-recompile by a reviewer.
- 2026-09-19: reorganized — moved workstation-wiki-storage.md, workstation-rollout.md, and install_llmwiki_workstation.py into private nested `my-docs/` (`synthet/my-docs`); added public private-docs.md pointer; gitignore `my-docs/`.
- 2026-09-19: created — workstation-wiki-storage.md capturing shared-root vs per-project storage (later moved to private my-docs).
- 2026-09-18: ingested — Ghidra Windows build notes plus local `README.md` / `application.properties`; added `D:/Projects/ghidra` to allowed_roots; compiled 8 candidate claims into entities `Ghidra` and `Ghidra workstation build`; validated and rendered with `--include-unreviewed`.
- 2026-09-15: created — workstation-rollout.md recording the LLM Wiki MCP/skill audit across D:\Projects; fixed .mcp.json `${workspaceFolder}` breakage and reconciled mcp-and-editors.md.

## 2026-07

- 2026-07-14: updated — regenerated agent-asset-inventory after skill consolidation (removed diagnosing-bugs/tdd duplicates; added karpathy-guidelines).

## 2026-06

- 2026-06-16: created — initial framework docs (README, INDEX, CANONICAL_SOURCES, OKF_ADOPTION, WIKI_SCHEMA, ai-workflow, security, project).
