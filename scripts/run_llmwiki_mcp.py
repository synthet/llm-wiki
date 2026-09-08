"""Launch the project MCP server relative to this checkout, independent of client cwd."""

from __future__ import annotations

import argparse
from pathlib import Path

from llmwiki.mcp_server import run_stdio


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-writes", action="store_true")
    parser.add_argument("--allow-review", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    run_stdio(root, allow_writes=args.allow_writes, allow_review=args.allow_review)


if __name__ == "__main__":
    main()
