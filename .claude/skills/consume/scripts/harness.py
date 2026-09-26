#!/usr/bin/env python3
"""Thin wrapper around scripts/wiki_ingest_pipeline.py for skill discovery."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
_SCRIPT = _REPO / "scripts" / "wiki_ingest_pipeline.py"

if __name__ == "__main__":
    sys.argv[0] = str(_SCRIPT)
    runpy.run_path(str(_SCRIPT), run_name="__main__")
