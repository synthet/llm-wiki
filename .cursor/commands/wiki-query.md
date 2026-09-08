---
capability: "wiki-query agent asset workflow"
side_effect_level: local_write
approval_required: false
requires_tools: "See asset body for tool requirements."
output_schema: "Markdown report or documented command output."
risk_class: medium
---

> **Cursor:** Same intent as Claude `/wiki-query`. When customizing, keep in sync with `.cursor/commands/wiki-query.md`.

# /wiki-query — Answer from reviewed canonical knowledge

Use `llmwiki ask`/MCP `ask` and cite exact immutable evidence. Do not answer factual questions from
generated pages or model memory when canonical reviewed evidence is insufficient.

## Inputs

- A question or topic from the user message.
- Optional explicit status filters for candidate/disputed/stale material.

## Steps

1. Run reviewed-only search before creating or compiling anything.
2. Use hierarchical tree traversal only when exact source evidence needs inspection.
3. Return the deterministic cited answer and retrieval trace ID.
4. If the result says `insufficient`, report that result rather than filling gaps.
5. Show non-reviewed status labels only when the user explicitly requested those states.

## Answer Format

Structure answers as:

```markdown
## Answer

[Synthesized response with citations]

### Sources

- [PAGE_NAME.md](path) — what this page contributed to the answer
- [PAGE_NAME.md](path) — what this page contributed to the answer
```

## Done when

- Every factual statement maps to returned evidence on one immutable source revision.
- Reviewed-only defaults were preserved or explicit non-reviewed filters are visible.

