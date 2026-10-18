---
name: framework-wiki-review
description: "Explicit framework workflow: wiki-review"
disable-model-invocation: true
capability: "framework-wiki-review agent asset workflow"
side_effect_level: local_write
approval_required: false
requires_tools: "See asset body for tool requirements."
output_schema: "Markdown report or documented command output."
risk_class: medium
---

# /wiki-review — Record explicit human review

List pending revisions with `llmwiki review list --json`. Before a state change, obtain the human
reviewer's supplied identity and rationale, inspect the exact claim revision and evidence, and run
`llmwiki review approve|reject|retract ID --reviewer NAME --note NOTE`. Never infer approval from an
LLM, automated validator, general write permission, or this command's invocation alone. Report the
review event UUID and exact before/after state, then validate and render through the application.
