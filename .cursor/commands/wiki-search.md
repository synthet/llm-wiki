# wiki-search

Search the LLM Wiki and answer grounded in the results.

Run from the repo root, then answer the user's question using the top hits,
citing page title and path. Prefer `reviewed` pages; flag any reliance on
`candidate`/`disputed` content.

```bash
PYTHONPATH=src python3 -m llmwiki.cli --root wiki index >/dev/null 2>&1
PYTHONPATH=src python3 -m llmwiki.cli --root wiki search "$ARGUMENTS" --expand --limit 8
```

Open the most relevant page with:

```bash
PYTHONPATH=src python3 -m llmwiki.cli --root wiki get "<title-or-id>"
```
