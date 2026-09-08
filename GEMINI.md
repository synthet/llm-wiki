# Gemini CLI compatibility

Gemini support is a thin adapter to the same `llmwiki` CLI/MCP services. It does not own schema,
state transitions, generated pages, or a separate workflow. Follow `AGENTS.md` and the canonical
`.claude/skills/llm-wiki/SKILL.md`; never edit generated `wiki/pages/` or `.llmwiki/` directly.

The `.gemini/commands/wiki/*.toml` commands call the installed `llmwiki` entry point. Keep these
manually owned adapters small. Claude assets remain canonical for generated Cursor/Codex mirrors.

