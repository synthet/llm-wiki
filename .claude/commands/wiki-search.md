---
description: Search the LLM Wiki and ground an answer in the results
argument-hint: <query>
allowed-tools: Bash(python3 -m llmwiki.cli:*), Read
---

Search the wiki for `$ARGUMENTS` and answer using the results.

Index (safe to re-run) and search:

```
!PYTHONPATH=src python3 -m llmwiki.cli --root wiki index >/dev/null 2>&1; PYTHONPATH=src python3 -m llmwiki.cli --root wiki search "$ARGUMENTS" --expand --limit 8
```

Then, if the top hits look relevant, open the most relevant page(s) with
`python3 -m llmwiki.cli --root wiki get "<title-or-id>"` and answer the user's
question, citing the page title and path. Prefer `reviewed` pages; if you rely on
a `candidate`/`disputed` page, say so explicitly.
