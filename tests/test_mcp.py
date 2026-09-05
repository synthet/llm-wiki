import io
import json

from llmwiki.mcp_server import MCPServer


def run(messages, root):
    stdin = io.StringIO("".join(json.dumps(m) + "\n" for m in messages))
    stdout = io.StringIO()
    MCPServer(default_root=root, stdin=stdin, stdout=stdout).serve()
    return [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]


def test_initialize_and_list(sample_wiki):
    out = run(
        [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2024-11-05"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ],
        sample_wiki,
    )
    init = next(o for o in out if o.get("id") == 1)
    assert init["result"]["serverInfo"]["name"] == "llmwiki"
    listed = next(o for o in out if o.get("id") == 2)
    names = {t["name"] for t in listed["result"]["tools"]}
    assert {"wiki_search", "wiki_validate", "wiki_get_page", "wiki_index"} <= names


def test_tool_call_validate(sample_wiki):
    out = run(
        [{"jsonrpc": "2.0", "id": 5, "method": "tools/call",
          "params": {"name": "wiki_validate", "arguments": {"strict": True}}}],
        sample_wiki,
    )
    res = out[0]["result"]
    assert res["isError"] is False
    assert res["structuredContent"]["ok"] is True


def test_tool_call_search(sample_wiki):
    # ensure index exists
    run([{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
          "params": {"name": "wiki_index", "arguments": {}}}], sample_wiki)
    out = run(
        [{"jsonrpc": "2.0", "id": 6, "method": "tools/call",
          "params": {"name": "wiki_search", "arguments": {"query": "frictionless", "limit": 3}}}],
        sample_wiki,
    )
    data = out[0]["result"]["structuredContent"]
    assert data["count"] >= 1


def test_unknown_method_errors(sample_wiki):
    out = run([{"jsonrpc": "2.0", "id": 9, "method": "no/such"}], sample_wiki)
    assert out[0]["error"]["code"] == -32601


def test_unknown_tool_errors(sample_wiki):
    out = run(
        [{"jsonrpc": "2.0", "id": 10, "method": "tools/call",
          "params": {"name": "nope", "arguments": {}}}],
        sample_wiki,
    )
    assert out[0]["error"]["code"] == -32602
