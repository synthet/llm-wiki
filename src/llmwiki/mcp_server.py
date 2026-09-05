"""A Model Context Protocol (MCP) server exposing the llmwiki tools.

Implemented with the standard library only: a JSON-RPC 2.0 loop over the
newline-delimited-JSON stdio transport that MCP clients (Claude Code, Cursor,
Gemini CLI, ...) speak. This keeps the server dependency-free and startable as
``llmwiki-mcp`` or ``llmwiki mcp`` or ``python -m llmwiki.mcp_server``.

Every tool mirrors a function in :mod:`llmwiki.ops`, so CLI and MCP behave
identically. Each tool accepts an optional ``root`` argument to override the
wiki root (otherwise ``LLMWIKI_ROOT`` or auto-discovery is used).
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import __version__, ops
from .wiki import Wiki

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "llmwiki"


# --------------------------------------------------------------------------- #
# Tool registry
# --------------------------------------------------------------------------- #
def _root(default_root: Optional[Path], args: Dict[str, Any]) -> Path:
    if args.get("root"):
        return Path(args["root"]).resolve()
    if default_root is not None:
        return default_root
    env = os.environ.get("LLMWIKI_ROOT")
    if env:
        return Path(env).resolve()
    return Wiki.discover().root


def build_tools(default_root: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    root_prop = {"root": {"type": "string", "description": "Override the wiki root directory."}}

    def tool(name, description, properties, handler, required=None):
        return {
            "name": name,
            "description": description,
            "inputSchema": {
                "type": "object",
                "properties": {**properties, **root_prop},
                "required": required or [],
                "additionalProperties": False,
            },
            "_handler": handler,
        }

    tools = [
        tool(
            "wiki_search",
            "Full-text + wikilink search over the compiled LLM Wiki. Returns "
            "ranked pages with snippets, review status and paths.",
            {
                "query": {"type": "string", "description": "Search query."},
                "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100},
                "status": {"type": "string", "description": "Filter by review status "
                           "(candidate|reviewed|disputed|stale|superseded|retracted)."},
                "type": {"type": "string", "description": "Filter by page type "
                         "(entity|topic|note|index)."},
                "expand": {"type": "boolean", "default": False,
                           "description": "Also return pages linked from the top hits."},
            },
            lambda a: ops.search(_root(default_root, a), a["query"],
                                 limit=int(a.get("limit", 10)), status=a.get("status"),
                                 type_=a.get("type"), expand=bool(a.get("expand", False))),
            required=["query"],
        ),
        tool(
            "wiki_get_page",
            "Fetch a single wiki page by id, slug, title or alias, including its "
            "claims, sources, links and (optionally) body.",
            {
                "ref": {"type": "string", "description": "id, slug, title or alias."},
                "body": {"type": "boolean", "default": True},
            },
            lambda a: ops.get_page(_root(default_root, a), a["ref"], body=bool(a.get("body", True))),
            required=["ref"],
        ),
        tool(
            "wiki_list_pages",
            "List wiki pages, optionally filtered by status, type or tag.",
            {
                "status": {"type": "string"},
                "type": {"type": "string"},
                "tag": {"type": "string"},
            },
            lambda a: ops.list_pages(_root(default_root, a), status=a.get("status"),
                                     type_=a.get("type"), tag=a.get("tag")),
        ),
        tool(
            "wiki_validate",
            "Lint-validate the wiki: frontmatter schema, review states, resolvable "
            "wikilinks, unique identity, claim→evidence coverage, freshness and "
            "rights. Returns issues grouped by severity; ok=false means errors.",
            {"strict": {"type": "boolean", "default": False,
                        "description": "Promote key warnings (missing evidence, stale) to errors."}},
            lambda a: ops.validate(_root(default_root, a), strict=bool(a.get("strict", False))),
        ),
        tool(
            "wiki_index",
            "Rebuild the search index (SQLite FTS5 or JSON fallback). Run after "
            "pages change so wiki_search reflects the latest content.",
            {},
            lambda a: ops.build_index(_root(default_root, a)),
        ),
        tool(
            "wiki_stats",
            "Wiki health metrics: page counts by status/type, citation coverage, "
            "broken wikilinks, orphan pages and index backend.",
            {},
            lambda a: ops.stats(_root(default_root, a)),
        ),
        tool(
            "wiki_backlinks",
            "Show the outbound links and backlinks of a page (the local wikilink "
            "graph around it).",
            {"ref": {"type": "string", "description": "id, slug, title or alias."}},
            lambda a: ops.backlinks(_root(default_root, a), a["ref"]),
            required=["ref"],
        ),
    ]
    return {t["name"]: t for t in tools}


# --------------------------------------------------------------------------- #
# JSON-RPC server loop
# --------------------------------------------------------------------------- #
class MCPServer:
    def __init__(self, default_root: Optional[Path] = None,
                 stdin=None, stdout=None):
        self.default_root = default_root
        self.tools = build_tools(default_root)
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self._initialized = False

    def log(self, *msg):
        print("[llmwiki-mcp]", *msg, file=sys.stderr, flush=True)

    def _send(self, obj: Dict[str, Any]) -> None:
        self.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self.stdout.flush()

    def _result(self, req_id, result) -> None:
        self._send({"jsonrpc": "2.0", "id": req_id, "result": result})

    def _error(self, req_id, code, message, data=None) -> None:
        err = {"code": code, "message": message}
        if data is not None:
            err["data"] = data
        self._send({"jsonrpc": "2.0", "id": req_id, "error": err})

    # -- dispatch ------------------------------------------------------------
    def handle(self, msg: Dict[str, Any]) -> None:
        method = msg.get("method")
        req_id = msg.get("id")
        params = msg.get("params") or {}

        # Notifications (no id) never get a response.
        if method == "notifications/initialized":
            self._initialized = True
            return
        if method and method.startswith("notifications/"):
            return

        if method == "initialize":
            return self._on_initialize(req_id, params)
        if method == "ping":
            return self._result(req_id, {})
        if method == "tools/list":
            return self._on_tools_list(req_id)
        if method == "tools/call":
            return self._on_tools_call(req_id, params)

        self._error(req_id, -32601, f"method not found: {method}")

    def _on_initialize(self, req_id, params) -> None:
        client_version = params.get("protocolVersion") or PROTOCOL_VERSION
        self._result(req_id, {
            "protocolVersion": client_version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": __version__},
            "instructions": (
                "Tools to search, read, validate and index a compiled LLM Wiki. "
                "Prefer wiki_search then wiki_get_page to ground answers in "
                "reviewed pages; run wiki_validate before committing changes and "
                "wiki_index after editing pages."
            ),
        })

    def _on_tools_list(self, req_id) -> None:
        public = []
        for t in self.tools.values():
            public.append({k: v for k, v in t.items() if not k.startswith("_")})
        self._result(req_id, {"tools": public})

    def _on_tools_call(self, req_id, params) -> None:
        name = params.get("name")
        args = params.get("arguments") or {}
        tool = self.tools.get(name)
        if tool is None:
            return self._error(req_id, -32602, f"unknown tool: {name}")
        try:
            data = tool["_handler"](args)
            text = json.dumps(data, indent=2, ensure_ascii=False)
            self._result(req_id, {
                "content": [{"type": "text", "text": text}],
                "structuredContent": data,
                "isError": False,
            })
        except Exception as exc:  # tool-level error -> return as tool result
            self.log("tool error:", name, repr(exc))
            self.log(traceback.format_exc())
            self._result(req_id, {
                "content": [{"type": "text", "text": f"error: {exc}"}],
                "isError": True,
            })

    # -- run -----------------------------------------------------------------
    def serve(self) -> int:
        self.log(f"serving v{__version__}; root={self.default_root or '(auto)'}")
        for line in self.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError as exc:
                self._error(None, -32700, f"parse error: {exc}")
                continue
            if isinstance(msg, list):  # batch
                for item in msg:
                    self.handle(item)
            else:
                self.handle(msg)
        return 0


def main(root: Optional[str] = None) -> int:
    default_root: Optional[Path] = None
    if root:
        default_root = Path(root).resolve()
    elif os.environ.get("LLMWIKI_ROOT"):
        default_root = Path(os.environ["LLMWIKI_ROOT"]).resolve()
    else:
        try:
            default_root = Wiki.discover().root
        except Exception:
            default_root = None
    return MCPServer(default_root=default_root).serve()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
