#!/usr/bin/env python3
"""Ingest the Image Scoring OKF bundle into the local LLM Wiki store."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "docs" / "ecosystems" / "image-scoring"


def main() -> int:
    if not BUNDLE.is_dir():
        print(f"ERROR: bundle missing: {BUNDLE}", file=sys.stderr)
        return 1

    md_files = sorted(BUNDLE.glob("*.md"))
    parent_index = ROOT / "docs" / "ecosystems" / "INDEX.md"
    if parent_index.is_file():
        md_files = [parent_index] + md_files
    if not md_files:
        print(f"ERROR: no markdown in {BUNDLE}", file=sys.stderr)
        return 1

    failed = 0
    for path in md_files:
        rel = path.relative_to(ROOT).as_posix()
        print(f"ingest {rel}")
        proc = subprocess.run(
            ["llmwiki", "ingest", str(path), "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            failed += 1
            print(proc.stdout or proc.stderr, file=sys.stderr)
        else:
            print(proc.stdout.strip()[:200])

    print(f"\nDone: {len(md_files) - failed}/{len(md_files)} ok")
    if failed:
        return 1
    print("Next: llmwiki validate && llmwiki render")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
