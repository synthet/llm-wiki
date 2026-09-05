# wiki-index

Rebuild the LLM Wiki search index and report health metrics.

```bash
PYTHONPATH=src python3 -m llmwiki.cli --root wiki index
PYTHONPATH=src python3 -m llmwiki.cli --root wiki stats
```

Summarise page counts by status/type, citation coverage, and any broken
wikilinks or orphan pages.
