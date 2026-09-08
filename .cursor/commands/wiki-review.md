---
capability: "review exact LLM Wiki claim revision"
side_effect_level: local_write
approval_required: true
requires_tools: "llmwiki CLI or llmwiki MCP review capability"
output_schema: "Review event with before/after state"
risk_class: high
---

# /wiki-review — Record explicit human review

List pending revisions with `llmwiki review list --json`. Before a state change, obtain the human
reviewer's supplied identity and rationale, inspect the exact claim revision and evidence, and run
`llmwiki review approve|reject|retract ID --reviewer NAME --note NOTE`. Never infer approval from an
LLM, automated validator, general write permission, or this command's invocation alone. Report the
review event UUID and exact before/after state, then validate and render through the application.
