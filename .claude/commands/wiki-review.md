---
description: Review candidate pages/claims and propose promotion to reviewed
argument-hint: [page title or id, optional]
allowed-tools: Bash(python3 -m llmwiki.cli:*), Read, Edit
---

Run the review loop for the LLM Wiki.

List what still needs review (or focus on `$ARGUMENTS` if given):

```
!PYTHONPATH=src python3 -m llmwiki.cli --root wiki list --status candidate
```

For each candidate page/claim:
1. Open it (`python3 -m llmwiki.cli --root wiki get "<ref>"`).
2. Check every claim against its cited evidence — does the source/locator
   actually support the `text`? Note anything unsupported.
3. Propose edits: fix or downgrade unsupported claims (`disputed`/`retracted`),
   then set well-supported claims and the page to `status: reviewed` and record
   the reviewer and date.

**Do not promote to `reviewed` without explicit human approval** — present your
assessment and the proposed diff first. After approval, apply edits, then run
`/wiki-lint` and `/wiki-index`.
