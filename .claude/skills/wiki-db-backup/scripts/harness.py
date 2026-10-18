#!/usr/bin/env python3
"""On-demand filesystem backup of LLM Wiki SQLite store (wiki.db + optional objects/)."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent / '_runtime'
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from llmwiki.config import discover_root  # noqa: E402

from scripts.skill_harness.io_util import emit  # noqa: E402

_WIKI_DB_NAMES = ("wiki.db", "wiki.db-wal", "wiki.db-shm")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_backup_base(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.expanduser().resolve()
    env = os.environ.get("LLMWIKI_DB_BACKUP_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    for drive in (Path("D:/Goolge Drive"), Path("D:/Google Drive")):
        if drive.is_dir():
            return (drive / "llm-wiki-backups" / "synthet-llm-wiki").resolve()
    raise FileNotFoundError(
        "No backup destination: pass --dest, set LLMWIKI_DB_BACKUP_ROOT, "
        "or create D:/Goolge Drive (or D:/Google Drive)."
    )


def plan_backup(
    wiki_root: Path,
    dest_base: Path,
    *,
    include_objects: bool,
) -> dict:
    llmwiki_dir = wiki_root / ".llmwiki"
    db_path = llmwiki_dir / "wiki.db"
    if not db_path.is_file():
        raise FileNotFoundError(f"Missing wiki database: {db_path}")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    backup_dir = dest_base / stamp

    files: list[dict] = []
    for name in _WIKI_DB_NAMES:
        src = llmwiki_dir / name
        if src.is_file():
            files.append(
                {
                    "source": str(src),
                    "target": str(backup_dir / name),
                    "bytes": src.stat().st_size,
                }
            )

    if include_objects:
        objects_src = llmwiki_dir / "objects"
        if objects_src.is_dir():
            files.append(
                {
                    "source": str(objects_src),
                    "target": str(backup_dir / "objects"),
                    "bytes": sum(p.stat().st_size for p in objects_src.rglob("*") if p.is_file()),
                    "kind": "directory",
                }
            )

    return {
        "wiki_root": str(wiki_root.resolve()),
        "llmwiki_dir": str(llmwiki_dir.resolve()),
        "dest_base": str(dest_base),
        "backup_dir": str(backup_dir),
        "include_objects": include_objects,
        "files": files,
    }


def run_backup(plan: dict) -> dict:
    backup_dir = Path(plan["backup_dir"])
    backup_dir.mkdir(parents=True, exist_ok=False)
    copied: list[dict] = []

    for entry in plan["files"]:
        src = Path(entry["source"])
        dst = Path(entry["target"])
        if entry.get("kind") == "directory":
            shutil.copytree(src, dst, dirs_exist_ok=False)
        else:
            shutil.copy2(src, dst)
        copied.append(
            {
                "path": str(dst),
                "bytes": dst.stat().st_size,
                "sha256": _sha256_file(dst) if dst.is_file() else None,
            }
        )

    wiki_db = backup_dir / "wiki.db"
    result = {
        **plan,
        "copied": copied,
        "wiki_db_sha256": _sha256_file(wiki_db) if wiki_db.is_file() else None,
        "dry_run": False,
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki-root", type=Path, default=None, help="Wiki root (default: discover)")
    parser.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="Backup base directory (timestamped subfolder created)",
    )
    parser.add_argument(
        "--include-objects",
        action="store_true",
        help="Also copy .llmwiki/objects/ (full byte restore)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Plan only; do not copy")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args(argv)

    try:
        wiki_root = discover_root(explicit=args.wiki_root)
        dest_base = resolve_backup_base(args.dest)
        plan = plan_backup(wiki_root, dest_base, include_objects=args.include_objects)
    except (FileNotFoundError, OSError) as exc:
        emit({"ok": False, "error": str(exc)}, as_json=args.json)
        return 1

    if args.dry_run:
        emit({"ok": True, "dry_run": True, **plan}, as_json=args.json)
        return 0

    try:
        result = run_backup(plan)
    except OSError as exc:
        emit({"ok": False, "error": str(exc), **plan}, as_json=args.json)
        return 1

    emit({"ok": True, **result}, as_json=args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
