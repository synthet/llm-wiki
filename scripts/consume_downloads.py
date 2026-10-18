#!/usr/bin/env python3
"""Reusable batch ingestion, markdown preservation, and verified cleanup for Downloads.

Safely feeds documents from D:/Downloads (or user Downloads) into the local LLM Wiki
(both SQLite db and Markdown notes under wiki/notes/_local/), while strictly guarding
sensitive personal files (financial, tax, IDs) and isolating reverse-engineering
topics to local-only storage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

# Ensure UTF-8 output encoding across platforms
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    os.environ["PYTHONUTF8"] = "1"

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from llmwiki.config import discover_root, ensure_within  # noqa: E402
from llmwiki.download_ingest import auto_compile_revisions  # noqa: E402
from llmwiki.service import WikiService  # noqa: E402

SUPPORTED_EXTENSIONS = {".md", ".markdown", ".txt", ".pdf"}

# Never ingest or touch sensitive personal documents
SENSITIVE_PATTERNS = [
    re.compile(r"estmt", re.IGNORECASE),
    re.compile(r"statement", re.IGNORECASE),
    re.compile(r"itin", re.IGNORECASE),
    re.compile(r"vtr_\d+", re.IGNORECASE),
    re.compile(r"tax", re.IGNORECASE),
    re.compile(r"irs", re.IGNORECASE),
    re.compile(r"invoice", re.IGNORECASE),
    re.compile(r"w2", re.IGNORECASE),
    re.compile(r"1099", re.IGNORECASE),
    re.compile(r"passport", re.IGNORECASE),
    re.compile(r"additional_information_letter", re.IGNORECASE),
]

REVERSE_ENGINEERING_PATTERNS = [
    re.compile(r"reverse", re.IGNORECASE),
    re.compile(r"reversing", re.IGNORECASE),
    re.compile(r"decompil", re.IGNORECASE),
    re.compile(r"disassembl", re.IGNORECASE),
    re.compile(r"ghidra", re.IGNORECASE),
    re.compile(r"enshrouded", re.IGNORECASE),
    re.compile(r"burstpick", re.IGNORECASE),
    re.compile(r"electron.*reverse", re.IGNORECASE),
]


CYRILLIC_PATTERN = re.compile(r"[\u0400-\u04ff]")


def is_sensitive(filename: str) -> bool:
    """Return True if filename looks like a sensitive financial, legal, or personal document."""
    if CYRILLIC_PATTERN.search(filename):
        return True
    return any(p.search(filename) for p in SENSITIVE_PATTERNS)


def is_reverse_engineering(filename: str) -> bool:
    """Return True if filename pertains to reverse engineering topics."""
    return any(p.search(filename) for p in REVERSE_ENGINEERING_PATTERNS)


def scan_downloads(directory: Path) -> tuple[list[Path], list[Path], list[Path]]:
    """Scan directory and categorize into: (eligible, sensitive_skipped, unsupported_skipped)."""
    eligible: list[Path] = []
    sensitive: list[Path] = []
    unsupported: list[Path] = []

    for item in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
        if not item.is_file():
            continue
        if item.suffix.lower() not in SUPPORTED_EXTENSIONS:
            unsupported.append(item)
            continue
        if is_sensitive(item.name):
            sensitive.append(item)
            continue
        eligible.append(item)

    return eligible, sensitive, unsupported


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def preserve_markdown_note(
    source_path: Path,
    wiki_root: Path,
    *,
    is_re: bool,
) -> Path:
    """Copy eligible markdown file to appropriate wiki/notes/_local/ directory."""
    if is_re:
        dest_dir = wiki_root / "wiki" / "notes" / "_local" / "reverse-engineering"
    else:
        dest_dir = wiki_root / "wiki" / "notes" / "_local" / "downloads"

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / source_path.name
    shutil.copy2(source_path, dest_file)
    return dest_file


def verify_file_in_store(service: WikiService, file_path: Path, digest: str) -> bool:
    """Verify that file digest exists in both source_revisions and physical objects/ store."""
    with service.store.transaction() as con:
        row = con.execute(
            "SELECT digest, content_path FROM source_revisions WHERE digest = ?",
            (digest,),
        ).fetchone()
        if not row:
            return False

        obj_path = service.config.db_path.parent / row["content_path"]
        if not obj_path.exists():
            return False
        return compute_sha256(obj_path) == digest


def run_pipeline(
    wiki_root: Path,
    downloads_dir: Path,
    *,
    execute: bool = False,
    cleanup: bool = False,
    auto_compile: bool = True,
    render: bool = True,
) -> dict[str, Any]:
    service = WikiService(wiki_root)
    ensure_within(downloads_dir.resolve(), service.config.allowed_roots)

    eligible, sensitive, unsupported = scan_downloads(downloads_dir)

    results: list[dict[str, Any]] = []
    preserved_notes: list[str] = []
    cleaned_up: list[str] = []
    revision_ids: list[str] = []

    if execute:
        for p in eligible:
            digest = compute_sha256(p)
            is_re = is_reverse_engineering(p.name)

            # 1. Ingest into wiki db
            try:
                ingest_res = service.ingest_file(p, rights="local_operator")
                rev_id = ingest_res.get("revision_id")
                if rev_id:
                    revision_ids.append(rev_id)
                ingest_ok = True
                err_msg = None
            except Exception as exc:
                ingest_ok = False
                err_msg = str(exc)
                ingest_res = {}

            # 2. If markdown, preserve in wiki/notes/_local/
            note_path = None
            if ingest_ok and p.suffix.lower() in {".md", ".markdown"}:
                try:
                    note = preserve_markdown_note(p, wiki_root, is_re=is_re)
                    note_path = str(note)
                    preserved_notes.append(note_path)
                except Exception as exc:
                    err_msg = f"Preserve note failed: {exc}"

            # 3. Verified cleanup
            deleted = False
            if ingest_ok and cleanup:
                if verify_file_in_store(service, p, digest):
                    try:
                        p.unlink()
                        deleted = True
                        cleaned_up.append(str(p))
                    except Exception as exc:
                        deleted = False
                        err_msg = f"Unlink failed: {exc}"

            results.append({
                "path": str(p),
                "name": p.name,
                "digest": digest,
                "is_reverse_engineering": is_re,
                "ingest_ok": ingest_ok,
                "error": err_msg,
                "preserved_note": note_path,
                "deleted": deleted,
            })

        # 4. Auto-compile candidate claims
        compiled_count = 0
        if auto_compile and revision_ids:
            try:
                comp = auto_compile_revisions(service, revision_ids)
                compiled_count = comp.get("count", 0)
            except Exception:
                compiled_count = 0

        # 5. Render projections
        rendered_count = 0
        if render:
            try:
                service.validate()
                rend = service.render(include_unreviewed=True)
                rendered_count = rend.get("count", 0)
            except Exception:
                rendered_count = 0

    return {
        "downloads_dir": str(downloads_dir),
        "execute": execute,
        "cleanup": cleanup,
        "eligible_count": len(eligible),
        "sensitive_skipped_count": len(sensitive),
        "sensitive_skipped": [p.name for p in sensitive],
        "unsupported_skipped_count": len(unsupported),
        "results": results,
        "preserved_notes_count": len(preserved_notes),
        "cleaned_up_count": len(cleaned_up),
        "cleaned_up": cleaned_up,
        "compiled_claims": compiled_count if execute else 0,
        "rendered_pages": rendered_count if execute else 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Feed documents from Downloads into local LLM Wiki (db + markdown) and clean originals."
    )
    parser.add_argument("--root", type=Path, help="Wiki root (default: current directory)")
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path("D:/Downloads"),
        help="Downloads folder to scan (default: D:/Downloads)",
    )
    parser.add_argument("--run", action="store_true", help="Execute ingestion and note preservation")
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Verify digests in store and remove original files from Downloads",
    )
    parser.add_argument("--no-compile", action="store_true", help="Skip candidate claim auto-compilation")
    parser.add_argument("--no-render", action="store_true", help="Skip projection rendering")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    root = discover_root(explicit=args.root)
    summary = run_pipeline(
        root,
        args.dir,
        execute=args.run,
        cleanup=args.cleanup,
        auto_compile=not args.no_compile,
        render=not args.no_render,
    )

    if args.as_json:
        json.dump(summary, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print(f"=== LLM Wiki Downloads Pipeline ===")
        print(f"Source Directory: {summary['downloads_dir']}")
        print(f"Mode: {'RUN (mutations enabled)' if summary['execute'] else 'DRY-RUN (no changes made)'}")
        print(f"Cleanup: {'ENABLED (verified originals removed)' if summary['cleanup'] else 'DISABLED'}")
        print(f"Eligible Documents: {summary['eligible_count']}")
        print(f"Protected Sensitive Files (SKIPPED): {summary['sensitive_skipped_count']}")
        for s in summary["sensitive_skipped"]:
            print(f"  [PROTECTED] {s}")
        print(f"Unsupported Files: {summary['unsupported_skipped_count']}")

        if summary["execute"]:
            print(f"\n--- Execution Outcomes ---")
            for r in summary["results"]:
                status = "OK" if r["ingest_ok"] else f"FAIL ({r['error']})"
                re_tag = " [REVERSE-ENG -> _local]" if r["is_reverse_engineering"] else ""
                clean_tag = " [DELETED]" if r["deleted"] else ""
                print(f"  [{status}]{re_tag}{clean_tag} {r['name']}")
            print(f"\nPreserved Markdown Notes: {summary['preserved_notes_count']}")
            print(f"Cleaned Up Downloads: {summary['cleaned_up_count']}")
            print(f"Compiled Candidate Claims: {summary['compiled_claims']}")
            print(f"Rendered Projections: {summary['rendered_pages']}")
        else:
            print("\n(Pass --run to ingest documents, or --run --cleanup to ingest and remove originals)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
