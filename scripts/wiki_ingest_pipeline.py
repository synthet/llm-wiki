#!/usr/bin/env python3
"""End-to-end batch ingestion, compilation, validation, rendering, and cleanup pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure UTF-8 output encoding across platforms
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from llmwiki.config import discover_root  # noqa: E402
from llmwiki.download_ingest import DEFAULT_EXTENSIONS, consume_download_pipeline  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="End-to-end pipeline: discover, ingest, compile, render, and safely clean up download documents"
    )
    parser.add_argument("--root", type=Path, help="Wiki root (default: discover from cwd)")
    parser.add_argument(
        "--dir",
        action="append",
        default=[],
        metavar="PATH",
        help="Specific directory to scan (must be within allowed_roots)",
    )
    parser.add_argument(
        "--extensions",
        default=",".join(DEFAULT_EXTENSIONS),
        help=f"Comma-separated list of extensions to include (default: {','.join(DEFAULT_EXTENSIONS)})",
    )
    parser.add_argument(
        "--no-discover",
        action="store_true",
        help="Do not auto-discover Downloads folders from allowed_roots",
    )
    parser.add_argument("--recursive", action="store_true", help="Include nested documents in subfolders")
    parser.add_argument("--max-files", type=int, default=200, metavar="N")
    parser.add_argument("--rights", default="unknown")
    parser.add_argument(
        "--run",
        action="store_true",
        help="Execute ingestion (default is dry-run plan only)",
    )
    parser.add_argument(
        "--auto-compile",
        action="store_true",
        help="Automatically formulate candidate claims with exact locators and compile into entities",
    )
    parser.add_argument(
        "--render",
        action="store_true",
        help="Validate store and render candidate/reviewed pages to wiki/pages/*.md",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Verify SHA-256 byte digest in .llmwiki/objects/ and safely remove processed files",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    exts = tuple(e.strip() for e in args.extensions.split(",") if e.strip())

    root = discover_root(explicit=args.root)
    payload = consume_download_pipeline(
        root,
        directories=[Path(p) for p in args.dir],
        extensions=exts,
        discover=not args.no_discover,
        recursive=args.recursive,
        max_files=args.max_files,
        rights=args.rights,
        run=args.run,
        auto_compile=args.auto_compile,
        render=args.render,
        cleanup=args.cleanup,
    )

    if args.as_json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print(f"wiki_root: {payload['wiki_root']}")
        print(f"directories ({len(payload['directories'])}):")
        for d in payload["directories"]:
            print(f"  - {d}")
        print(f"extensions: {payload['extensions']}")
        print(f"files: {payload['file_count']} ({payload['ingestable_count']} ingestable)")

        if not args.run:
            print("mode: dry-run (pass --run to ingest)")
            for row in payload.get("plan", []):
                flag = "ok" if row["ingestable"] else f"skip ({row['reason']})"
                print(f"  [{flag}] {row['path']}")
        else:
            print(f"ingested: {payload.get('ingested', 0)}, failed: {payload.get('failed', 0)}")
            print(f"compiled claims: {payload.get('compiled_claims', 0)}")
            print(f"rendered pages: {payload.get('rendered_pages', 0)}")
            print(f"cleaned files: {payload.get('cleaned_files', 0)}")
            for row in payload.get("results", []):
                status = "ok" if row.get("ok") else "err"
                print(f"  [{status}] {row['path']}")

    failed = payload.get("failed", 0) if args.run else 0
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
