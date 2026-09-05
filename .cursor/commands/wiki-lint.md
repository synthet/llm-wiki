# wiki-lint

Validate the LLM Wiki and fix any reported errors.

```bash
PYTHONPATH=src python3 -m llmwiki.cli --root wiki lint --strict
```

Fix each error by editing pages under `wiki/pages/` (see `docs/schema.md`):
broken wikilinks, missing claim evidence, duplicate ids/slugs, invalid
status/type, or stale freshness. Re-run until it prints `OK`, then rebuild:

```bash
PYTHONPATH=src python3 -m llmwiki.cli --root wiki index
```
