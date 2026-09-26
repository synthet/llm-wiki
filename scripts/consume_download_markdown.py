#!/usr/bin/env python3
"""Ingest markdown from Downloads-style folders into the local LLM Wiki."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from llmwiki.config import discover_root  # noqa: E402
from llmwiki.download_ingest import consume_download_markdown  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Discover and ingest markdown files from Downloads directories"
    )
    parser.add_argument("--root", type=Path, help="Wiki root (default: discover from cwd)")
    parser.add_argument(
        "--dir",
        action="append",
        default=[],
        metavar="PATH",
        help="Additional directory to scan (must fall under allowed_roots)",
    )
    parser.add_argument(
        "--no-discover",
        action="store_true",
        help="Do not auto-discover Downloads folders from allowed_roots",
    )
    parser.add_argument("--recursive", action="store_true", help="Include markdown in subfolders")
    parser.add_argument("--max-files", type=int, default=200, metavar="N")
    parser.add_argument("--rights", default="unknown")
    parser.add_argument(
        "--run",
        action="store_true",
        help="Ingest files (default is dry-run plan only)",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    root = discover_root(explicit=args.root)
    payload = consume_download_markdown(
        root,
        directories=[Path(p) for p in args.dir],
        discover=not args.no_discover,
        recursive=args.recursive,
        max_files=args.max_files,
        rights=args.rights,
        run=args.run,
    )
    if args.as_json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print(f"wiki_root: {payload['wiki_root']}")
        print(f"directories: {len(payload['directories'])}")
        for d in payload["directories"]:
            print(f"  - {d}")
        print(f"files: {payload['file_count']} ({payload['ingestable_count']} ingestable)")
        if not args.run:
            print("dry-run (pass --run to ingest)")
            for row in payload.get("plan", []):
                flag = "ok" if row["ingestable"] else f"skip ({row['reason']})"
                print(f"  [{flag}] {row['path']}")
        else:
            print(f"ingested: {payload.get('ingested', 0)}, failed: {payload.get('failed', 0)}")
            for row in payload.get("results", []):
                status = "ok" if row.get("ok") else "err"
                print(f"  [{status}] {row['path']}")

    failed = payload.get("failed", 0) if args.run else 0
    skipped = payload["file_count"] - payload["ingestable_count"]
    if failed or (args.run and skipped):
        return 1 if failed else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
