from __future__ import annotations

import sys
from pathlib import Path

import pytest
from conftest import proposal, unwrap_tool
from mcp import Client, StdioServerParameters

from llmwiki.mcp_server import create_server
from llmwiki.service import WikiService


@pytest.mark.asyncio
async def test_mcp_typed_tools_templates_and_independent_gates(tmp_path: Path):
    WikiService.init(tmp_path)
    server = create_server(tmp_path)
    async with Client(server) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}
        assert {"search", "ask", "ingest_path", "approve_claim"} <= names
        ingest = next(tool for tool in tools.tools if tool.name == "ingest_path")
        assert ingest.input_schema["properties"]["path"]["type"] == "string"
        templates = await client.list_resource_templates()
        assert any(str(item.uri_template).startswith("llmwiki://sources/") for item in templates.resource_templates)
        denied_write = unwrap_tool(await client.call_tool("ingest_path", {"path": "x"}))
        assert denied_write["error"]["code"] == "write_capability_required"
        denied_review = unwrap_tool(
            await client.call_tool(
                "approve_claim",
                {"claim_revision_id": "x", "reviewer": "R", "note": "N"},
            )
        )
        assert denied_review["error"]["code"] == "review_capability_required"


@pytest.mark.asyncio
async def test_mcp_pagination_root_boundary_response_limit_and_redaction(tmp_path: Path, monkeypatch):
    WikiService.init(tmp_path)
    server = create_server(tmp_path, allow_writes=True, max_response_bytes=200)
    async with Client(server) as client:
        invalid_page = unwrap_tool(await client.call_tool("list_sources", {"limit": 9999}))
        assert invalid_page["error"]["code"] == "invalid_pagination"
        escaped = unwrap_tool(await client.call_tool("export_backup", {"relative_path": "../escape.json"}))
        assert escaped["error"]["code"] == "path_outside_wiki_root"
        too_large = unwrap_tool(await client.call_tool("stats", {}))
        assert too_large["error"]["code"] == "response_too_large"

    def explode(self):
        raise RuntimeError("SECRET-INTERNAL-DETAIL")

    monkeypatch.setattr(WikiService, "stats", explode)
    redacting_server = create_server(tmp_path)
    async with Client(redacting_server) as client:
        redacted = unwrap_tool(await client.call_tool("stats", {}))
        assert redacted["error"]["code"] == "internal_error"
        assert "SECRET" not in str(redacted)


@pytest.mark.asyncio
async def test_real_stdio_offline_acceptance_flow(tmp_path: Path):
    WikiService.init(tmp_path)
    source = tmp_path / "evidence.md"
    text = "# Corvids\n\nRavens remember human faces.\n"
    source.write_text(text, encoding="utf-8")
    params = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "llmwiki.cli",
            "--root",
            str(tmp_path),
            "mcp",
            "--allow-writes",
            "--allow-review",
        ],
    )
    async with Client(params) as client:
        ingested = unwrap_tool(await client.call_tool("ingest_path", {"path": str(source)}))
        revision_id = ingested["result"]["result"]["revision_id"]
        nodes = unwrap_tool(await client.call_tool("list_tree_nodes", {"revision_id": revision_id, "limit": 100}))
        root_node = nodes["result"]["items"][0]
        sections = unwrap_tool(
            await client.call_tool(
                "list_tree_nodes",
                {"revision_id": revision_id, "parent_id": root_node["id"], "limit": 100},
            )
        )
        section = sections["result"]["items"][0]
        leaves = unwrap_tool(
            await client.call_tool(
                "list_tree_nodes",
                {"revision_id": revision_id, "parent_id": section["id"], "limit": 100},
            )
        )
        leaf = next(item for item in leaves["result"]["items"] if "Ravens" in item["heading"])
        read = unwrap_tool(await client.call_tool("read_tree_node", {"node_id": leaf["id"]}))
        assert read["result"]["text"] == "Ravens remember human faces."
        exported = unwrap_tool(await client.call_tool("export_compilation_request", {"revision_ids": [revision_id]}))[
            "result"
        ]
        evidence_leaf = next(item for item in exported["evidence_bundle"] if "Ravens" in item["text"])
        applied = unwrap_tool(
            await client.call_tool("apply_compilation_result", {"proposal": proposal(exported, evidence_leaf)})
        )
        claim_id = applied["result"]["claim_revision_ids"][0]
        rendered = unwrap_tool(await client.call_tool("render", {}))
        assert rendered["result"]["status"] == "completed"
        approved = unwrap_tool(
            await client.call_tool(
                "approve_claim",
                {"claim_revision_id": claim_id, "reviewer": "E2E", "note": "Exact text checked"},
            )
        )
        assert approved["result"]["after"] == "reviewed"
        answer = unwrap_tool(await client.call_tool("ask", {"question": "Which birds remember faces?"}))
        assert answer["result"]["insufficient"] is False
        assert answer["result"]["citations"][0]["evidence"][0]["source_revision_id"] == revision_id
