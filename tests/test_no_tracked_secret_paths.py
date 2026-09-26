"""Tracked paths must not include gitignored secret or machine-local config files."""

from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.skill_harness.verify_catalog import is_secret_path

REPO = Path(__file__).resolve().parents[1]


def test_git_index_excludes_secret_paths():
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    tracked = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    violations = [path for path in tracked if is_secret_path(path)]
    assert not violations, (
        "Secret or machine-local paths are tracked in git (remove with "
        "`git rm --cached <path>` and keep them in .gitignore): "
        + ", ".join(violations)
    )
