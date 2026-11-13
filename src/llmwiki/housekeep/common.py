"""Shared plumbing for the housekeeping tools (synthet-code-framework docs/housekeeping-protocol.md).

Plans and manifests are ASCII JSON. ``describe`` asks a read-only synthet-agent-swarm agent about
redacted staging files; the agent's reply is untrusted text and is redacted and re-checked before it is
stored. Jev decides from the payload ``jev_payload`` builds; ``decide`` merges its answers.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .redact import redact, residual

EXIT_OK, EXIT_FAILED, EXIT_INPUT, EXIT_PREREQ = 0, 1, 2, 3
BATCH = 20  # synthet-agent-swarm `files` limit


class HousekeepExit(Exception):
    """Carry a protocol exit code and a JSON payload back to the CLI."""

    def __init__(self, code: int, payload: dict[str, Any]):
        super().__init__(payload.get("error", ""))
        self.code = code
        self.payload = payload


def today() -> str:
    return dt.date.today().isoformat()


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def load(path: Path | str) -> dict[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HousekeepExit(
            EXIT_INPUT, {"ok": False, "error": f"cannot read {Path(path).name}: {type(exc).__name__}"}
        ) from exc


def save(path: Path | str, data: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=1, ensure_ascii=True), encoding="utf-8")


def run(cmd: list[str], *, cwd: Path | str | None = None, env: dict[str, str] | None = None, timeout: int = 120):
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "", repr(exc)


# --------------------------------------------------------------------------- describe
def swarm_command(arg: str | None) -> list[str] | None:
    if arg:
        return ["node", arg] if arg.endswith(".js") else [arg]
    env = os.environ.get("HK_SWARM_CMD")
    return json.loads(env) if env else None


def parse_reply(reply: str) -> dict[str, Any]:
    start, end = reply.find("{"), reply.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        data = json.loads(reply[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def clean_agent_text(text: Any, limit: int) -> str | None:
    """Agent output is untrusted: redact it, cap it, and refuse it if anything risky survives."""
    if not isinstance(text, str) or not text.strip():
        return None
    cleaned = redact(text)[:limit]
    return None if residual(cleaned) else cleaned


def run_describe(
    staging: Path,
    names: list[str],
    task: str,
    *,
    swarm: list[str] | None,
    harness: str = "claude",
    timeout_ms: int = 300_000,
    budget_usd: float = 0,
    model_chain: str | None = None,
    dry_run: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Describe staging files in batches. Returns (reply-by-file, per-batch errors)."""
    batches = [names[i : i + BATCH] for i in range(0, len(names), BATCH)]
    replies: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []
    for n, batch in enumerate(batches):
        request: dict[str, Any] = {
            "task": task,
            "files": batch,
            "harnesses": [harness],
            "mode": "explain",
            "timeoutMs": timeout_ms,
        }
        if budget_usd:
            request["budgetUsd"] = round(budget_usd / len(batches), 2)
        if model_chain:
            request["modelChains"] = {harness: model_chain.split(",")}
        request_path = staging / f"request-{n}.json"
        save(request_path, request)
        if dry_run or not swarm:
            continue
        rc, out, err = run(
            [*swarm, "run", "--request", str(request_path)],
            env={**os.environ, "WORKSPACE_ROOT": str(staging)},
            timeout=timeout_ms // 1000 + 60,
        )
        try:
            response = json.loads(out.splitlines()[-1]) if out else {}
        except json.JSONDecodeError:
            response = {}
        got = parse_reply(response.get("reply") or "") if response.get("ok") else {}
        replies.update({k: v for k, v in got.items() if k in batch})
        if not got:
            errors.append(
                {
                    "batch": n,
                    "exit": rc,
                    "outcomes": [h.get("outcome") for h in response.get("harnesses", [])],
                    "stderr": err[-300:],
                }
            )
    return replies, errors


# --------------------------------------------------------------------------- jev / decide
def jev_payload(
    plan: dict[str, Any], context: str, option_text: dict[str, str], evidence_keys: list[str]
) -> dict[str, Any]:
    state: dict[str, Any] = {"context": context, "items": {}}
    questions: dict[str, Any] = {}
    for item in plan["items"]:
        if item["action"] != "decide":
            continue
        evidence = {k: item[k] for k in evidence_keys if item.get(k) not in (None, [], "")}
        evidence.update({k: v for k, v in item.get("evidence", {}).items() if v not in (None, [], "")})
        state["items"][item["id"]] = evidence
        questions[item["id"]] = {
            "type": "choice",
            "instructions": f"Decide what to do with item {item['id']} in state.items.",
            "criteria": {o: option_text.get(o, o) for o in item["options"]},
        }
    return {"state": state, "questions": questions}


def decide(plan: dict[str, Any], answers: dict[str, Any], *, min_confidence: float, gated: set[str]) -> dict[str, Any]:
    answers = answers.get("result", answers)
    answers = answers.get("answers", answers)
    for item in plan["items"]:
        answer = answers.get(item["id"])
        if item["action"] != "decide" or not isinstance(answer, dict):
            continue
        choice, confidence = answer.get("choice"), float(answer.get("confidence") or 0)
        item["jev"] = {"choice": choice, "confidence": confidence, "probabilities": answer.get("probabilities")}
        if choice not in item["options"] or confidence < min_confidence or choice == "keep":
            item["action"], item["why"] = "hold", f"jev {choice} at {confidence:.2f}"
        else:
            item["action"] = choice
            item["needs_approval"] = choice in gated
    return {
        "held": [i["id"] for i in plan["items"] if i["action"] == "hold"],
        "needs_owner_approval": [i["id"] for i in plan["items"] if i.get("needs_approval")],
    }


def summary(plan: dict[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for item in plan["items"]:
        key = f"{item['kind']}:{item['action']}"
        counts[key] = counts.get(key, 0) + 1
    return {"plan_items": len(plan["items"]), "by_kind_action": dict(sorted(counts.items()))}
