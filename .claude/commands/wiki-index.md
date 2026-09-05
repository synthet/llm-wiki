---
description: Rebuild the LLM Wiki search index and show health stats
allowed-tools: Bash(python3 -m llmwiki.cli:*)
---

Rebuild the search index and report wiki health:

```
!PYTHONPATH=src python3 -m llmwiki.cli --root wiki index && echo && PYTHONPATH=src python3 -m llmwiki.cli --root wiki stats
```

Summarise for the user: page counts by status/type, citation coverage, and any
broken wikilinks or orphan pages worth addressing.
