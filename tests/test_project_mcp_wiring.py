"""Committed editor configs must wire llmwiki-ro-core to the checkout launcher."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _load_mcp_json(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def test_mcp_json_servers_include_llmwiki_launcher():
    for rel in (".mcp.json", ".cursor/mcp.example.json"):
        servers = _load_mcp_json(rel)["mcpServers"]
        server = servers["llmwiki-ro-core"]
        assert server["command"] == "uv"
        args = server["args"]
        assert "run_llmwiki_mcp.py" in " ".join(args)


def test_codex_config_declares_llmwiki_mcp():
    text = (REPO / ".codex/config.toml").read_text(encoding="utf-8")
    assert "[mcp_servers.llmwiki-ro-core]" in text
    assert "run_llmwiki_mcp.py" in text
    assert '"--project"' in text or "'--project'" in text or "--project" in text


@pytest.mark.parametrize(
    "rel",
    [
        ".gemini/commands/wiki/search.toml",
        ".gemini/commands/wiki/ingest.toml",
        ".gemini/commands/wiki/validate.toml",
        ".gemini/commands/wiki/review.toml",
    ],
)
def test_gemini_wiki_commands_reference_llmwiki(rel: str):
    body = (REPO / rel).read_text(encoding="utf-8")
    assert "llmwiki" in body
