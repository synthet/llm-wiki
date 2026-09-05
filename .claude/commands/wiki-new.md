---
description: Create a new candidate wiki page from a title
argument-hint: <page title>
allowed-tools: Bash(python3 -m llmwiki.cli:*), Read, Edit
---

Create a new page for `$ARGUMENTS`:

```
!PYTHONPATH=src python3 -m llmwiki.cli --root wiki new "$ARGUMENTS"
```

Then open the created file and fill it in:
- Choose the right `type` (`entity` for a thing/tool/org, `topic` for a concept,
  `note` otherwise).
- Add `sources` (uri + `sha256:` digest + rights) and atomic `claims` with
  `evidence`. Keep `status: candidate`.
- Add `[[Wikilinks]]` to existing related pages (check with
  `python3 -m llmwiki.cli --root wiki list`).

Finish with `/wiki-lint` and `/wiki-index`.
