---
description: Lint-validate the LLM Wiki and fix any errors
allowed-tools: Bash(python3 -m llmwiki.cli:*), Read, Edit
---

Validate the wiki structure, provenance and links:

```
!PYTHONPATH=src python3 -m llmwiki.cli --root wiki lint --strict
```

If there are errors, fix them by editing the offending pages under `wiki/pages/`:
- `broken-wikilink` → correct the target or create the missing page.
- `missing-evidence` → add `evidence` (source id + locator) to the claim, or set
  its status back to `candidate`.
- `duplicate-id` / `duplicate-slug` → give each page a unique identity.
- `invalid-status` / `invalid-type` → use a value from `docs/schema.md`.
- `stale` → refresh the source and update `freshness`, or mark the page `stale`.

Re-run until it reports `OK`, then rebuild the index:

```
!PYTHONPATH=src python3 -m llmwiki.cli --root wiki index
```
