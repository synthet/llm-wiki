---
type: Guide
title: Private docs location
description: Where operator-private documentation lives relative to the public LLM Wiki checkout.
resource: private-docs.md
tags: [docs, private, workstation]
timestamp: 2026-09-19T00:00:00Z
okf_version: 0.1
---

# Private docs (operator)

Operator-private documentation is **not** in this public `docs/` tree.

It lives in the private repo [synthet/my-docs](https://github.com/synthet/my-docs)
(`git@github.com:synthet/my-docs.git`), nested locally as a **gitignored sub-repository**:

```text
<llm-wiki-checkout>/my-docs/
```

Clone once (requires access to the private repo):

```bash
git clone git@github.com:synthet/my-docs.git my-docs
```

Do not commit `my-docs/` into `synthet/llm-wiki` (ignored; not a submodule — keeps the private URL
out of the public tree). Product docs and contracts remain here under `docs/`.
