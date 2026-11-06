# Wiki activity log

Append-only. One line per wiki restructure, newest under the current month.
Format: `- YYYY-MM-DD: <verb> — <details and paths>` (verbs: `created`, `updated`, `ingested`,
`lint-fixed`, `reorganized`).

## 2026-10

- 2026-10-23: ingested - Nikon Z8 vs Z6II AFInfo (0x0088) and AFInfo2 (0x00B7) technical specification (`wiki/notes/_local/downloads/deep-research-report (15).md`); source_id 56691562-2a01-4833-b6dd-5a50504aa8f6, revision 586d5075-2662-4d2e-97a2-9e6f817ac53b; compiled 1 candidate claims; validated (0 issues); rendered with `--include-unreviewed`; verified SHA-256 and removed original from D:/Downloads.
- 2026-10-23: ingested - Nikon AFInfo2 (0x00B7) MakerNote specification and AF area decoding (`wiki/notes/_local/downloads/deep-research-report (15).md`); source_id 56691562-2a01-4833-b6dd-5a50504aa8f6, revision 1e9627d2-4fac-4d10-a56a-947b8178e46a; compiled 1 candidate claims; validated (0 issues); rendered with `--include-unreviewed`; verified SHA-256 and removed original from D:/Downloads.
- 2026-10-23: ingested - LightCraft Nikon Z8 and Z6 II NEF support review (wiki/notes/_local/downloads/lightcraft-nikon-z8-z6ii-nef-support.md); source_id d264cd90-6cdd-4af9-8009-d871ee6bc4ca, revision 6d0bfd1d-d491-4736-8bce-f23fe3bce2de; compiled 1 candidate claim; validated (0 issues); rendered with --include-unreviewed; verified SHA-256 and removed original from D:/Downloads.
- 2026-10-19: ingested — Cursor agent updater liveness (`wiki/notes/cursor-agent-updater-liveness-2026-10-19.md`); compiled 15 candidate claims into entity `Cursor agent updater`; validated and rendered with `--include-unreviewed`.
- 2026-10-18: ingested — Antigravity (37 articles), Codex (95 articles), Claude Code (528 articles), and deep-research-report (2).md; backed up .llmwiki/wiki.db and objects/ to D:/Goolge Drive/llm-wiki-backups/synthet-llm-wiki/2026-10-18_014459/.
- 2026-10-10: ingested — 80 sanitized historical session notes; complete originals privately archived with SHA-256 receipts; immutable revisions verified; validate/render completed. Private indexes are kept with the ignored source notes.
- 2026-10-05: ingested — `/consume` markdown from `C:/Users/dmnsy/Downloads` and `D:/Downloads` (13 files, reused revisions, SHA-256 verified cleanup); backed up `.llmwiki/wiki.db` to `D:/Goolge Drive/llm-wiki-backups/synthet-llm-wiki/2026-10-05_193357/`.

## 2026-09

- 2026-09-27: created — comprehensive OKF bundle `docs/ecosystems/image-scoring/` (13 pages: canonical sources, products, hub, MCP/Jev, operations, infrastructure); `scripts/ingest_image_scoring_ecosystem.py`; hub `image-scoring/scripts/llmwiki-sync-ecosystem.ps1`; added `D:/Projects/image-scoring` to `.llmwiki` allowed_roots.
- 2026-09-24: ingested — `/consume` batch from `D:/Downloads` (53 files scanned, 49 ingested, 42 candidate claims compiled, 115 pages rendered); 4 encrypted PDFs skipped (`VTR_146.pdf`, `VTR_146 2.pdf`, two untitled PDFs); validated store clean; Downloads not cleaned up.
- 2026-09-24: maintained — `/consume --cleanup` on `D:/Downloads`: SHA-256 verified and removed 49 ingested files from disk; 4 encrypted PDFs left in Downloads.
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

- 2026-10-23: created — model/pipeline/skills synergy research (2026-10-23), explicit checkout snapshots, primary-source candidate compilation and a local-only session supplement; linked from the Image Scoring bundle.

- 2026-10-24: updated — consolidated the architecture/focus campaign from three authorized hub sources into 14 candidate claims; canonical validation found zero errors and rendering completed for 145 pages. Full sibling specs remain in their owning repositories because direct ingestion was outside configured source roots. Receipt: `wiki/notes/architecture-focus-campaign-2026-10-24.md`.

- 2026-10-25: updated — ingested the Vexlum data-mining audit (`D:/Downloads/vexlum-mining-bundle/vexlum-data-mining-report.md`, revision `ce6a3b41`) and its source `model-suitability-2026-10-25.json` (revision `47781712`), rights unknown. Compiled 12 candidate claims on `Vexlum image quality models` and `Vexlum score analytics dashboard`; headline figures were recomputed independently from the JSON before compiling. Validation found zero errors; render produced 146 pages.

- 2026-11-03: updated — ingested the eye model benchmark note (`wiki/notes/eye-model-benchmark-2026-11-02.md`, revision `d4f9d377`) from `image-scoring-model` into 28 candidate claims under the `Eye Model Benchmark 2026-11` entity; validation found zero errors and rendering completed. An earlier revision of the same note (`c34bb5cf`) has no claims.

- 2026-11-03: updated — corrected the eye model benchmark note (revision `2ec5b1e0`): calibration frame n0016 is a cat, so the claim that verified_negatives_v1 had an error is contradicted by a new claim; the old candidate needs owner retraction. Also records bird-only calibration numbers and the eye-model and training-gate status.

- 2026-11-03: updated — ingested the Vexlum MCP and UI E2E session note (`wiki/notes/vexlum-mcp-and-ui-e2e-2026-11-03.md`, revision `4f4efbe6`) into 29 candidate claims under `Vexlum MCP entry point` and `Vexlum UI E2E suite`; PR #784 and #768 were open at compile time. Validation found zero errors; rendering completed for 149 pages.

- 2026-11-03: updated — added the fresh-label confirmation to the eye model benchmark note (revision `0b2dc0dc`): the strict detector-agreement rule drops too many birds, and the light rule is the fleet candidate.

- 2026-11-03: updated — added the per-crop check result and pipeline issue links to the eye model benchmark note (revision `fb13bb56`).

- 2026-11-03: updated — refreshed the Vexlum MCP and UI E2E note (revision `07117353`) after PRs #784, #768 and #794 merged, adding the headless defaults and the #785 run results; 34 candidate claims replace the 29 from revision `4f4efbe6`, which are now stale. Validation found zero errors; rendering completed for 149 pages.
