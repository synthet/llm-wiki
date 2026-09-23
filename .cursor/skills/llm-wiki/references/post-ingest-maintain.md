# Post-ingest maintain checklist

Load when compiling claims or closing an "update llm wiki" / `/wiki-maintain` loop.

## Evidence locators

1. Read the immutable source text for the revision (not a paraphrased note of it).
2. Choose a quote that is a single contiguous substring supporting one atomic claim.
3. Compute `start`/`end` against that source so `source[start:end] == quote` exactly.
4. Prefer one bullet or one sentence; do not start mid-bullet or spill into the next bullet.
5. After `compile --apply-result`, sample several claims from the rendered page or `get` output
   and verify the quote still matches.

## Claim repair paths

| Situation | Allowed path |
|-----------|--------------|
| Same claim text, better evidence | Dedup will reuse the old revision — reword the claim text slightly **or** retract then recompile |
| Candidate with wrong evidence | `llmwiki review retract <id> --reviewer <human> --note "..."` then compile a new candidate |
| Candidate -> superseded | Invalid — not allowed |
| Need reviewed status | Only with explicit human reviewer identity via `/wiki-review` |

Never invent `--reviewer`.

## Render convention in this checkout

Generated pages currently label claim status inline. While most claims are `candidate`, render with
`--include-unreviewed` so new entities appear. Switch to reviewed-only render when the operator asks
for reviewed-only projections.

## Docs vs product wiki

| Path | Role |
|------|------|
| `docs/` | Living OKF docs: INDEX, README, log, contracts |
| `wiki/notes/` | Handwritten sources; ingest to become canonical |
| `wiki/pages/` | Generated only via `llmwiki render` |
| `.llmwiki/` | SQLite + objects; never edit by hand |

## Commands

- `/wiki-ingest` — bring one source in
- `/wiki-maintain` — validate, render, index, log
- `/wiki-lint` — structural / full docs health
- `/wiki-review` — human approve/reject/retract
- `/wiki-query` — answer from reviewed claims
