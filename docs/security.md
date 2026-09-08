---
type: Technical Reference
title: Security Model
description: Security model, secret-handling rules, and the pre-merge security review checklist.
resource: security.md
tags: [docs, security]
timestamp: 2026-06-16T00:00:00Z
okf_version: 0.1
---

# Security

## Secrets

- Secrets live in `secrets.json` / `.env` (git-ignored), never in committed config or code.
- Use `.env.example` for non-secret defaults.
- Secrets never appear in logs, tool output, audit logs, or external-review payloads.


## Agent permission model

- **Default read-only mode:** the scaffolded `.claude/settings.json` allowlist permits only repository inspection (`Bash(git status)`, `Bash(git diff:*)`, `Bash(git log:*)`) and `WebSearch`.
- **Opt-in local writes:** maintainers can opt into local repository writes by copying or merging `.claude/settings.write.example.json` into the active Claude settings. Treat `git add` and `git commit` as local write permissions and enable only for tasks that need them.
- **Remote writes are distinct:** `gh pr`, `gh issue`, and `gh project` mutate remote GitHub state, can notify collaborators, and can trigger automations. They require explicit task intent and target verification; local-write approval alone is insufficient.
- **External export requires explicit approval:** before sending code, prompts, logs, artifacts, generated reports, or review bundles to external providers, obtain explicit approval and verify no secrets or proprietary material are included.
- **Seeded-project default:** projects bootstrapped from this framework inherit the safer read-only `.claude/settings.json` unless a maintainer deliberately opts into write-capable settings.

## Hard rules

- Validate every external input against a schema; reject malformed payloads (fail-closed).
- Write/side-effecting operations require explicit confirmation and an allowlist.
- No raw shell / arbitrary-code tools without an approval policy.
- Never modify `.git/config` (see [`../.agent/SAFETY.md`](../.agent/SAFETY.md)).

## Product threat model

### Untrusted sources and prompt injection

Every ingested byte is data. LLM Wiki decodes/extracts supported formats but never runs document
macros, scripts, commands, shell fragments, links, or model-like instructions. Provider prompts
explicitly delimit source text as untrusted evidence. Imported proposals are schema/identity/
locator validated before one atomic mutation; model output cannot grant `reviewed` status.

### File boundaries and resource exhaustion

Configured `allowed_roots` are resolved before local acquisition. Traversal and symlink escapes fail
closed. File/download byte limits, PDF page limits, redirect caps, and parse/HTTP timeouts bound
resource use. Media detection checks the PDF signature and rejects binary/NUL text rather than
trusting the extension or HTTP header alone. Invalid/encrypted PDFs are rejected; no-text PDFs
return `ocr_required` and are not sent to an OCR service.

### URL ingestion and SSRF

URL ingestion is explicit and fetches one resource without crawling. Only HTTP(S), without URL
credentials, is accepted. Every redirect hostname is resolved and all results must be globally
routable; loopback, private, link-local, reserved, and metadata-service-style addresses are
blocked. Resolution is checked again during acquisition, environment proxy inheritance is disabled,
and downloads stream through a byte limit. Local provider mode rejects URL ingestion entirely.

DNS/IP validation reduces SSRF exposure but is not a substitute for an OS/network egress policy in
hostile multi-tenant environments. Run behind an outbound firewall for high-assurance isolation.

### Provider and secret boundaries

Agent mode makes zero model calls. API mode calls only the configured OpenAI-compatible endpoint.
Local mode accepts only a loopback endpoint and never falls back remotely. Credential values come
from a named environment variable, are not persisted, and are excluded from safe errors. Requests,
tokens, time, and retries are bounded; missing usage/cost data remains unknown.

### Canonical integrity and capabilities

Original objects are SHA-256 verified. Evidence bounds and exact quotes are revalidated before
review. Generated-page digests prevent silent overwrite of manual edits. MCP fixes one wiki root,
caps responses, validates typed inputs through the maintained SDK, redacts unexpected exceptions,
and gates ordinary canonical writes separately from human review authority.

## Review checklist (pre-merge)

- [ ] No secrets, tokens, or credentials in the diff.
- [ ] New inputs validated; injection/path-traversal considered.
- [ ] No new undocumented network calls or secret-storage locations.
- [ ] Side-effecting actions gated behind confirmation/approval.
- [ ] Logs/outputs redact sensitive values.

For new features touching MCP/tools/hooks/remote surfaces, run the
[`threat-modeling-agentic-tools`](../.claude/skills/threat-modeling-agentic-tools/SKILL.md) skill.
