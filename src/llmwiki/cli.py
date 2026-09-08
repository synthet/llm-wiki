"""Stable command-line adapter for the shared application services."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .config import discover_root
from .errors import LLMWikiError, error
from .providers import ProviderConfig
from .service import WikiService

EXIT_CODES = {"not_found": 4, "security": 5, "provider": 6, "conflict": 3, "input": 2}


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="llmwiki", description="Local-first evidence-bound LLM Wiki")
    ap.add_argument("--root", type=Path, help="Wiki root (otherwise discovered from current directory)")
    ap.add_argument("--json", action="store_true", help="Emit compact machine-readable JSON")
    ap.add_argument("--mode", choices=("agent", "api", "local"), default=os.getenv("LLMWIKI_MODE", "agent"))
    ap.add_argument("--endpoint", default=os.getenv("LLMWIKI_ENDPOINT"))
    ap.add_argument("--api-key-env", default=os.getenv("LLMWIKI_API_KEY_ENV"))
    ap.add_argument("--compiler-model", default=os.getenv("LLMWIKI_COMPILER_MODEL"))
    ap.add_argument("--retrieval-model", default=os.getenv("LLMWIKI_RETRIEVAL_MODEL"))
    commands = ap.add_subparsers(dest="command", required=True)
    commands.add_parser("init").add_argument("--force", action="store_true")
    new = commands.add_parser("new")
    new.add_argument("title")
    new.add_argument("--alias", action="append", default=[])
    ingest = commands.add_parser("ingest")
    ingest.add_argument("resource")
    ingest.add_argument("--url", action="store_true")
    ingest.add_argument("--rights", default="unknown")
    ingest.add_argument("--source-id")
    ingest.add_argument("--no-wait", action="store_true")
    ingest.add_argument("--idempotency-key")
    sources = commands.add_parser("sources")
    sources.add_argument("--id")
    _page_args(sources)
    compile_cmd = commands.add_parser("compile")
    compile_cmd.add_argument("--revision-id", action="append")
    compile_cmd.add_argument("--export-request", nargs="?", const="-")
    compile_cmd.add_argument("--apply-result", type=Path)
    compile_cmd.add_argument("--no-wait", action="store_true")
    ask = commands.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--limit", type=int, default=8)
    ask.add_argument("--include-status", action="append")
    review = commands.add_parser("review")
    review_commands = review.add_subparsers(dest="review_command", required=True)
    review_list = review_commands.add_parser("list")
    _page_args(review_list)
    for name in ("approve", "reject", "retract"):
        action = review_commands.add_parser(name)
        action.add_argument("claim_revision_id")
        action.add_argument("--reviewer", required=True)
        action.add_argument("--note", required=True)
    refresh = commands.add_parser("refresh")
    refresh.add_argument("--source-id")
    refresh.add_argument("--no-wait", action="store_true")
    render = commands.add_parser("render")
    render.add_argument("--include-unreviewed", action="store_true")
    render.add_argument("--no-wait", action="store_true")
    export = commands.add_parser("export")
    export.add_argument("path", type=Path)
    import_cmd = commands.add_parser("import")
    import_cmd.add_argument("path", type=Path)
    import_cmd.add_argument("--format", choices=("json", "markdown"), default="json")
    import_cmd.add_argument("--no-wait", action="store_true")
    jobs = commands.add_parser("jobs")
    _page_args(jobs)
    job = commands.add_parser("job")
    job_commands = job.add_subparsers(dest="job_command", required=True)
    job_commands.add_parser("get").add_argument("job_id")
    job_commands.add_parser("cancel").add_argument("job_id")
    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--include-status", action="append")
    search.add_argument("--tree", action="store_true")
    commands.add_parser("index")
    commands.add_parser("lint")
    commands.add_parser("validate")
    commands.add_parser("stats")
    get = commands.add_parser("get")
    get.add_argument("ref")
    list_cmd = commands.add_parser("list")
    list_cmd.add_argument("--status")
    _page_args(list_cmd)
    links = commands.add_parser("links")
    links.add_argument("ref")
    commands.add_parser("rules")
    mcp = commands.add_parser("mcp")
    mcp.add_argument("--allow-writes", action="store_true")
    mcp.add_argument("--allow-review", action="store_true")
    return ap


def _page_args(command: argparse.ArgumentParser) -> None:
    command.add_argument("--limit", type=int, default=50)
    command.add_argument("--offset", type=int, default=0)


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    raw, json_output, extracted_root = _extract_portable_globals(raw)
    args = parser().parse_args(raw)
    args.json = args.json or json_output
    if extracted_root is not None:
        args.root = extracted_root
    root = discover_root(explicit=args.root)
    try:
        if args.command == "init":
            payload = WikiService.init(root, force=args.force)
        else:
            service = WikiService(
                root,
                ProviderConfig(
                    mode=args.mode,
                    endpoint=args.endpoint,
                    api_key_env=args.api_key_env,
                    compiler_model=args.compiler_model,
                    retrieval_model=args.retrieval_model,
                ),
            )
            payload = _dispatch(service, args)
        if payload is not None:
            _emit({"ok": True, "result": payload}, compact=args.json)
        return 0
    except LLMWikiError as exc:
        _emit({"ok": False, "error": exc.as_dict()}, compact=args.json, stream=sys.stderr)
        return _exit_code(exc.code)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        safe = error(
            "invalid_input",
            "The requested operation could not parse its local input.",
            reason=type(exc).__name__,
        )
        _emit({"ok": False, "error": safe.as_dict()}, compact=args.json, stream=sys.stderr)
        return 2


def _dispatch(service: WikiService, args: argparse.Namespace) -> dict[str, Any] | None:
    command = args.command
    if command == "mcp":
        from .mcp_server import run_stdio

        run_stdio(service.config.root, allow_writes=args.allow_writes, allow_review=args.allow_review)
        return None
    if command == "new":
        return service.new_entity(args.title, args.alias)
    if command == "ingest":
        kind = "ingest_url" if args.url else "ingest_file"
        request = ({"url": args.resource} if args.url else {"path": args.resource}) | {"rights": args.rights}
        if args.source_id:
            if args.no_wait:
                raise error("invalid_input", "--source-id cannot be combined with --no-wait.")
            return (
                service.ingest_url(args.resource, source_id=args.source_id, rights=args.rights)
                if args.url
                else service.ingest_file(Path(args.resource), source_id=args.source_id, rights=args.rights)
            )
        return service.submit_job(kind, request, idempotency_key=args.idempotency_key, wait=not args.no_wait)
    if command == "sources":
        return service.get_source(args.id) if args.id else service.list_sources(args.limit, args.offset)
    if command == "compile":
        if args.apply_result and args.export_request:
            raise error("invalid_input", "Choose either --apply-result or --export-request.")
        if args.apply_result:
            return service.compile_apply(json.loads(args.apply_result.read_text(encoding="utf-8")))
        if args.export_request is not None:
            request = service.compile_export(args.revision_id)
            if args.export_request != "-":
                Path(args.export_request).write_text(
                    json.dumps(request, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8",
                )
                return {"path": args.export_request, "run_id": request["run_id"]}
            return request
        return service.submit_job("compile", {"revision_ids": args.revision_id}, wait=not args.no_wait)
    if command == "ask":
        return service.ask(args.question, limit=args.limit, statuses=args.include_status)
    if command == "review":
        if args.review_command == "list":
            return service.review_list(args.limit, args.offset)
        return service.review(args.claim_revision_id, args.review_command, reviewer=args.reviewer, note=args.note)
    if command == "refresh":
        return service.submit_job("refresh", {"source_id": args.source_id}, wait=not args.no_wait)
    if command == "render":
        return service.submit_job("render", {"include_unreviewed": args.include_unreviewed}, wait=not args.no_wait)
    if command == "export":
        return service.export_json(args.path)
    if command == "import":
        if args.format == "markdown":
            if args.no_wait:
                raise error("invalid_input", "Markdown migration does not support --no-wait.")
            return service.import_markdown(args.path)
        if args.no_wait:
            raise error("invalid_input", "Backup restore requires the foreground empty-store check.")
        return service.import_json(args.path)
    if command == "jobs":
        return service.store.list_jobs(args.limit, args.offset)
    if command == "job":
        return service.store.get_job(args.job_id) if args.job_command == "get" else service.cancel_job(args.job_id)
    if command == "search":
        return service.search(args.query, limit=args.limit, statuses=args.include_status, include_nodes=args.tree)
    if command == "index":
        return service.rebuild_index()
    if command in {"lint", "validate"}:
        return service.validate()
    if command == "stats":
        return service.stats()
    if command == "get":
        return service.get_page(args.ref)
    if command == "list":
        return service.list_pages(status=args.status, limit=args.limit, offset=args.offset)
    if command == "links":
        return service.backlinks(args.ref)
    if command == "rules":
        return service.rules()
    raise error("unknown_command", "Unknown command.")


def _extract_portable_globals(argv: list[str]) -> tuple[list[str], bool, Path | None]:
    result: list[str] = []
    json_output = False
    root: Path | None = None
    index = 0
    while index < len(argv):
        if argv[index] == "--json":
            json_output = True
            index += 1
            continue
        if argv[index] == "--root":
            if index + 1 >= len(argv):
                raise SystemExit("--root requires a path")
            root = Path(argv[index + 1])
            index += 2
            continue
        result.append(argv[index])
        index += 1
    return result, json_output, root


def _emit(payload: dict[str, Any], *, compact: bool, stream=None) -> None:
    stream = stream or sys.stdout
    options = {"ensure_ascii": False, "sort_keys": True}
    if compact:
        print(json.dumps(payload, separators=(",", ":"), **options), file=stream)
    else:
        print(json.dumps(payload, indent=2, **options), file=stream)


def _exit_code(code: str) -> int:
    if "not_found" in code or code.endswith("_missing"):
        return EXIT_CODES["not_found"]
    if any(token in code for token in ("forbidden", "ssrf", "outside", "escape", "capability")):
        return EXIT_CODES["security"]
    if code.startswith("provider") or "endpoint" in code or "credential" in code:
        return EXIT_CODES["provider"]
    if "conflict" in code or "stale" in code:
        return EXIT_CODES["conflict"]
    return EXIT_CODES["input"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
