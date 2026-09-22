---
type: Guide
title: Private wiki location
description: Where the private wiki tree lives relative to the public LLM Wiki checkout.
resource: private-docs.md
tags: [docs, private, workstation, wiki]
timestamp: 2026-09-21T00:00:00Z
okf_version: 0.1
---

# Private wiki (operator)

Private handwritten notes and operator hubs are **not** in this public `docs/` tree.

They live in the private repo [synthet/my-docs](https://github.com/synthet/my-docs)
(`git@github.com:synthet/my-docs.git`), nested locally as a **gitignored sub-repository at
`wiki/`** (the path the product already uses for notes/pages):

```text
<llm-wiki-checkout>/wiki/
```

There is no separate `my-docs/` folder. Clone once (requires access to the private repo):

```bash
git clone git@github.com:synthet/my-docs.git wiki
```

Do not commit `wiki/` into `synthet/llm-wiki` (ignored; not a submodule — keeps the private URL
out of the public tree). Product docs and contracts remain here under `docs/`. Generated
`wiki/pages/*.md` stay local and regenerable from `.llmwiki`.
