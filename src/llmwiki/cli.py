"""Command-line interface for llmwiki.

    llmwiki init [dir]
    llmwiki new "Title" [--type entity] [--status candidate] [-o path]
    llmwiki index
    llmwiki search QUERY [--limit N] [--status S] [--type T] [--expand] [--json]
    llmwiki lint [--strict] [--json]      (alias: validate)
    llmwiki stats [--json]
    llmwiki get REF [--json] [--no-body]
    llmwiki list [--status S] [--type T] [--tag T] [--json]
    llmwiki links REF [--json]
    llmwiki mcp                           (run the MCP server over stdio)

All commands accept ``--root DIR`` to point at a wiki; otherwise the nearest
wiki root at or above the current directory is auto-discovered.
"""

from __future__ import annotations

import argparse
import json as _json
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__, ops
from .lint import RULES
from .templates import init_wiki, new_page
from .wiki import Wiki


def _resolve_root(args) -> Path:
    if getattr(args, "root", None):
        return Path(args.root).resolve()
    return Wiki.discover().root


def _emit(data, as_json: bool, plain_fn=None):
    if as_json or plain_fn is None:
        print(_json.dumps(data, indent=2, ensure_ascii=False))
    else:
        plain_fn(data)


# --------------------------------------------------------------------------- #
# command handlers
# --------------------------------------------------------------------------- #
def cmd_init(args) -> int:
    root = Path(args.dir or ".").resolve()
    created = init_wiki(root)
    if created:
        print(f"Initialised wiki at {root}")
        for kind, path in created.items():
            print(f"  + {kind}: {path}")
    else:
        print(f"Wiki already initialised at {root}")
    return 0


def cmd_new(args) -> int:
    text = new_page(args.title, type_=args.type, status=args.status)
    if args.output:
        out = Path(args.output)
    else:
        root = _resolve_root(args)
        out = Wiki(root).page_root()
        from .model import slugify
        out = out / f"{slugify(args.title)}.md"
    if out.exists() and not args.force:
        print(f"error: {out} already exists (use --force)", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"Created {out}")
    return 0


def cmd_index(args) -> int:
    root = _resolve_root(args)
    result = ops.build_index(root)
    _emit(result, args.json, lambda d: print(
        f"Indexed {d['pages_indexed']} pages ({d['backend']}) -> {d['index_dir']}"))
    return 0


def cmd_search(args) -> int:
    root = _resolve_root(args)
    try:
        data = ops.search(root, args.query, limit=args.limit, status=args.status,
                          type_=args.type, expand=args.expand)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    def plain(d):
        if not d["results"]:
            print("No matches.")
            return
        top = max((r["score"] for r in d["results"]), default=0) or 1
        for r in d["results"]:
            rel = 100 * r["score"] / top  # normalised relevance vs. best hit
            flag = " ~" if r["matched_via"] == "wikilink" else "  "
            print(f"{rel:>5.1f}{flag} [{r['status']}] {r['title']}  ({r['path']})")
            if r["snippet"]:
                print(f"         {r['snippet']}")

    _emit(data, args.json, plain)
    return 0


def cmd_lint(args) -> int:
    root = _resolve_root(args)
    data = ops.validate(root, strict=args.strict)

    def plain(d):
        for issue in d["issues"]:
            loc = f"{issue['path']}:{issue['line']}" if issue["line"] else issue["path"]
            print(f"{loc}: {issue['severity']}: [{issue['rule']}] {issue['message']}")
        c = d["counts"]
        print(f"\n{d['pages']} pages checked — "
              f"{c['error']} error(s), {c['warning']} warning(s), {c['info']} info")
        print("OK" if d["ok"] else "FAILED")

    _emit(data, args.json, plain)
    return 0 if data["ok"] else 1


def cmd_stats(args) -> int:
    root = _resolve_root(args)
    data = ops.stats(root)

    def plain(d):
        print(f"pages:              {d['pages']}")
        print(f"  by status:        {d['by_status']}")
        print(f"  by type:          {d['by_type']}")
        print(f"claims:             {d['claims']} "
              f"({d['claims_with_evidence']} with evidence)")
        cov = d["citation_coverage"]
        print(f"citation coverage:  {cov if cov is not None else 'n/a'}")
        print(f"sources:            {d['sources']}")
        print(f"wikilinks:          {d['wikilinks']} "
              f"({d['broken_wikilinks']} broken)")
        print(f"orphan pages:       {len(d['orphan_pages'])}")
        print(f"index:              {d['index_backend']} "
              f"({'present' if d['index_present'] else 'missing'})")

    _emit(data, args.json, plain)
    return 0


def cmd_get(args) -> int:
    root = _resolve_root(args)
    data = ops.get_page(root, args.ref, body=not args.no_body)
    if not data["found"]:
        print(f"error: no page matching '{args.ref}'", file=sys.stderr)
        return 1

    def plain(d):
        print(f"# {d['title']}  [{d['status']}]")
        print(f"id: {d['id']}   type: {d['type']}   path: {d['path']}")
        if d["tags"]:
            print(f"tags: {', '.join(d['tags'])}")
        if d["claims"]:
            print(f"claims: {len(d['claims'])}")
        if d["outbound_links"]:
            print(f"links: {', '.join(d['outbound_links'])}")
        if d["backlinks"]:
            print(f"backlinks: {', '.join(d['backlinks'])}")
        if "body" in d:
            print("\n" + d["body"].strip())

    _emit(data, args.json, plain)
    return 0


def cmd_list(args) -> int:
    root = _resolve_root(args)
    data = ops.list_pages(root, status=args.status, type_=args.type, tag=args.tag)

    def plain(d):
        for p in d["pages"]:
            print(f"[{p['status']:<10}] {p['type']:<6} {p['title']}  ({p['path']})")
        print(f"\n{d['count']} page(s)")

    _emit(data, args.json, plain)
    return 0


def cmd_links(args) -> int:
    root = _resolve_root(args)
    data = ops.backlinks(root, args.ref)
    if not data["found"]:
        print(f"error: no page matching '{args.ref}'", file=sys.stderr)
        return 1

    def plain(d):
        print(f"# {d['title']}")
        print("outbound:")
        for p in d["outbound"]:
            print(f"  -> {p['title']}  ({p['path']})")
        print("backlinks:")
        for p in d["backlinks"]:
            print(f"  <- {p['title']}  ({p['path']})")

    _emit(data, args.json, plain)
    return 0


def cmd_rules(args) -> int:
    for rule, desc in RULES.items():
        print(f"{rule:<22} {desc}")
    return 0


def cmd_mcp(args) -> int:
    from .mcp_server import main as mcp_main
    return mcp_main(root=getattr(args, "root", None))


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="llmwiki", description="Index, lint and search an LLM Wiki.")
    p.add_argument("--version", action="version", version=f"llmwiki {__version__}")
    p.add_argument("--root", help="wiki root (default: auto-discover)")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("init", help="scaffold a new wiki")
    sp.add_argument("dir", nargs="?", help="directory to initialise (default: .)")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("new", help="create a new page from the template")
    sp.add_argument("title")
    sp.add_argument("--type", default="note", help="entity|topic|note|index")
    sp.add_argument("--status", default="candidate")
    sp.add_argument("-o", "--output", help="output file path")
    sp.add_argument("--force", action="store_true")
    sp.set_defaults(func=cmd_new)

    sp = sub.add_parser("index", help="(re)build the search index")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_index)

    sp = sub.add_parser("search", help="full-text + wikilink search")
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=10)
    sp.add_argument("--status")
    sp.add_argument("--type", dest="type")
    sp.add_argument("--expand", action="store_true", help="expand results via wikilinks")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_search)

    for name in ("lint", "validate"):
        sp = sub.add_parser(name, help="validate wiki structure and provenance")
        sp.add_argument("--strict", action="store_true", help="promote key warnings to errors")
        sp.add_argument("--json", action="store_true")
        sp.set_defaults(func=cmd_lint)

    sp = sub.add_parser("stats", help="show wiki health metrics")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_stats)

    sp = sub.add_parser("get", help="print a page by id/slug/title/alias")
    sp.add_argument("ref")
    sp.add_argument("--no-body", action="store_true")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_get)

    sp = sub.add_parser("list", help="list pages")
    sp.add_argument("--status")
    sp.add_argument("--type", dest="type")
    sp.add_argument("--tag")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("links", help="show backlinks/outbound links of a page")
    sp.add_argument("ref")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_links)

    sp = sub.add_parser("rules", help="list linter rules")
    sp.set_defaults(func=cmd_rules)

    sp = sub.add_parser("mcp", help="run the MCP server over stdio")
    sp.set_defaults(func=cmd_mcp)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except BrokenPipeError:  # pragma: no cover
        return 0
    except KeyboardInterrupt:  # pragma: no cover
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
