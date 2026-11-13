"""`llmwiki housekeep <task> <step>` argument parsing and dispatch."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from . import transcripts


def add_parser(commands: argparse._SubParsersAction) -> None:
    housekeep = commands.add_parser("housekeep", help="Per-domain housekeeping (docs/housekeeping-protocol.md)")
    tasks = housekeep.add_subparsers(dest="housekeep_task", required=True)
    tr = tasks.add_parser("transcripts", help="Stale agent-session exports -> private wiki notes")
    steps = tr.add_subparsers(dest="housekeep_step", required=True)

    scan = steps.add_parser("scan")
    scan.add_argument("--scan-root", type=Path, action="append", required=True, help="Projects root; repeatable")
    scan.add_argument("--out", type=Path, required=True)
    scan.add_argument("--min-age-days", type=int, default=7)
    scan.add_argument("--max-files", type=int, default=20_000, help="Bound on candidate files sampled")
    scan.add_argument("--max-depth", type=int, default=4, help="Folders deeper than this below a root are skipped")
    scan.add_argument("--include-docs", action="store_true")
    scan.add_argument("--allow-full", action="store_true", help="Offer ingest_redacted_full as an option")

    describe = steps.add_parser("describe")
    describe.add_argument("--plan", type=Path, required=True)
    describe.add_argument("--swarm", help="synthet-agent-swarm dist/index.js (or HK_SWARM_CMD)")
    describe.add_argument("--staging", type=Path)
    describe.add_argument("--harness", default="claude")
    describe.add_argument("--model-chain")
    describe.add_argument("--max-items", type=int, default=40)
    describe.add_argument("--budget-usd", type=float, default=0)
    describe.add_argument("--timeout-ms", type=int, default=300_000)
    describe.add_argument("--refresh", action="store_true")
    describe.add_argument("--dry-run", action="store_true")

    steps.add_parser("jev").add_argument("--plan", type=Path, required=True)

    decide = steps.add_parser("decide")
    decide.add_argument("--plan", type=Path, required=True)
    decide.add_argument("--answers", type=Path, required=True)
    decide.add_argument("--min-confidence", type=float, default=0.5)

    apply = steps.add_parser("apply")
    apply.add_argument("--plan", type=Path, required=True)
    apply.add_argument("--apply", action="store_true", help="Act; without it this is a dry run")
    apply.add_argument("--compile", action="store_true", help="Also extract candidate claims from each note")
    apply.add_argument("--backup-name", help="Backup folder name under <scan-root>/_backup")

    for name in ("verify", "restore"):
        steps.add_parser(name).add_argument("--manifest", type=Path, required=True)

    purge = steps.add_parser("purge")
    purge.add_argument("--manifest", type=Path, required=True)
    purge.add_argument("--approve", default="")
    purge.add_argument("--approval-note", default="")
    purge.add_argument("--apply", action="store_true")


def dispatch(service: Any, args: argparse.Namespace) -> dict[str, Any]:
    step = args.housekeep_step
    if step == "scan":
        return transcripts.scan(
            args.scan_root,
            args.out,
            min_age_days=args.min_age_days,
            max_files=args.max_files,
            max_depth=args.max_depth,
            include_docs=args.include_docs,
            allow_full=args.allow_full,
        )
    if step == "describe":
        return transcripts.describe(
            args.plan,
            args.staging,
            swarm_arg=args.swarm,
            max_items=args.max_items,
            budget_usd=args.budget_usd,
            timeout_ms=args.timeout_ms,
            harness=args.harness,
            model_chain=args.model_chain,
            refresh=args.refresh,
            dry_run=args.dry_run,
        )
    if step == "jev":
        return transcripts.jev(args.plan)
    if step == "decide":
        return transcripts.decide_cmd(args.plan, args.answers, args.min_confidence)
    if step == "apply":
        return transcripts.apply(
            args.plan, service, do=args.apply, compile_claims=args.compile, backup_name=args.backup_name
        )
    if step == "verify":
        return transcripts.verify(args.manifest, service)
    if step == "restore":
        return transcripts.restore(args.manifest)
    return transcripts.purge(
        args.manifest, service, approve=args.approve, approval_note=args.approval_note, do=args.apply
    )
