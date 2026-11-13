"""`llmwiki housekeep transcripts`: detection, redaction, describe, apply, verify, restore, purge."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from llmwiki.cli import main as cli_main
from llmwiki.housekeep import transcripts
from llmwiki.housekeep.common import HousekeepExit
from llmwiki.housekeep.redact import redact, residual
from llmwiki.service import WikiService

TOKEN = "ghp_" + "Zq9" * 13
PEM_BODY = "MIIEowIBAAKCAQEAq7Lr0Qw9" + "Kp3x" * 10
RANDOM = "Qm7Zr2Lx9Pw4Kd8Vt1Bn6Hy3Jc5Gf0Sa"
PASSWORD = "opalriver77"
EMAIL = "someone.private@mailhost.org"
OLD = time.time() - 30 * 86400


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def env(tmp_path: Path):
    WikiService.init(tmp_path)
    service = WikiService(tmp_path)
    projects = tmp_path / "projects"
    app = projects / "app"
    app.mkdir(parents=True)
    git(app, "init", "-q")
    session = app / "2026-10-01-120000-debug-session.md"
    session.write_text(
        "## User\nWhy does the test flake?\n\n## Assistant\n"
        f"Found it. token {TOKEN} and key\n-----BEGIN RSA PRIVATE KEY-----\n{PEM_BODY}\n-----END RSA PRIVATE KEY-----\n"
        f"Home {Path.home()} mail {EMAIL} blob {RANDOM}\nThe clock was not pinned.\n",
        encoding="utf-8",
    )
    rollout = app / "rollout-abc.jsonl"
    rollout.write_text(
        json.dumps({"message": {"role": "user", "content": f"set DB_PASSWORD={PASSWORD} please"}})
        + "\n"
        + json.dumps({"message": {"role": "assistant", "content": "done"}})
        + "\n",
        encoding="utf-8",
    )
    tracked = app / "tracked-chat.md"
    tracked.write_text("## User\nhi\n\n## Assistant\nhello\n", encoding="utf-8")
    git(app, "add", "tracked-chat.md")
    git(app, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "chat")
    fresh = app / "2026-11-12-100000-live.md"
    fresh.write_text("## User\nnow\n\n## Assistant\nworking\n", encoding="utf-8")
    (app / "notes.md").write_text("# Notes\nplain notes\n", encoding="utf-8")
    for p in (session, rollout, tracked):
        os.utime(p, (OLD, OLD))
    stub = tmp_path / "stub_swarm.py"
    stub.write_text(
        "import json, os, sys\n"
        "req = json.load(open(sys.argv[sys.argv.index('--request') + 1], encoding='utf-8'))\n"
        "ws = os.environ['WORKSPACE_ROOT']\n"
        "out = {}\n"
        "for f in req['files']:\n"
        "    first = open(os.path.join(ws, f), encoding='utf-8').read().splitlines()[0]\n"
        f"    summary = 'The flaky test was fixed by pinning the clock. Leaked {TOKEN}.'\n"
        "    out[f] = {'description': 'describes ' + first, 'summary': summary}\n"
        "ok = [{'id': 'claude', 'ok': True, 'outcome': 'ok'}]\n"
        "print(json.dumps({'ok': True, 'harnesses': ok, 'reply': json.dumps(out)}))\n",
        encoding="utf-8",
    )
    os.environ["HK_SWARM_CMD"] = json.dumps([sys.executable, str(stub)])
    yield {
        "root": tmp_path,
        "service": service,
        "projects": projects,
        "app": app,
        "session": session,
        "rollout": rollout,
        "plan": tmp_path / "scratch" / "plan.json",
        "staging": tmp_path / "scratch" / "stage",
    }
    os.environ.pop("HK_SWARM_CMD", None)


def items_by_name(plan_path: Path) -> dict[str, dict]:
    return {i["name"]: i for i in json.loads(plan_path.read_text(encoding="utf-8"))["items"]}


def test_redact_catches_every_planted_secret():
    text = redact(
        f"a {TOKEN}\n-----BEGIN RSA PRIVATE KEY-----\n{PEM_BODY}\n-----END RSA PRIVATE KEY-----\n"
        f"user: set DB_PASSWORD={PASSWORD} now {RANDOM} {EMAIL} 192.168.1.20 C:\\Users\\alice\\x"
    )
    for secret in (TOKEN, PEM_BODY, PASSWORD, RANDOM, EMAIL, "192.168.1.20", "alice"):
        assert secret not in text
    assert residual(text) == []


def test_identity_terms_are_redacted_and_fail_closed(monkeypatch):
    from llmwiki.housekeep import redact as redact_module

    monkeypatch.setenv("HK_REDACT_TERMS", "quillmoss,HOSTBRAVO")
    redact_module.identity_terms.cache_clear()
    try:
        raw = (
            'run as HOSTBRAVO\\quillmoss; path "\\u0027C:\\\\Users\\\\quillmoss\\\\.gemini"'
            ' and grep -Pattern "quillmoss" review-cusersquillmossappdata.txt list\\nquillmoss\\n'
        )
        text = redact(raw)
        assert "quillmoss" not in text.lower() and "hostbravo" not in text.lower()
        assert residual("hello quillmoss") == ["local identity term"]
    finally:
        monkeypatch.delenv("HK_REDACT_TERMS")
        redact_module.identity_terms.cache_clear()


def test_scan_respects_max_depth(env):
    deep = env["app"] / "a" / "b" / "c" / "d"
    deep.mkdir(parents=True)
    old = deep / "2026-10-02-120000-deep.md"
    old.write_text("## User\nq\n\n## Assistant\na\n", encoding="utf-8")
    os.utime(old, (OLD, OLD))
    transcripts.scan([env["projects"]], env["plan"], max_depth=4)
    assert old.name not in items_by_name(env["plan"])
    transcripts.scan([env["projects"]], env["plan"], max_depth=8)
    assert old.name in items_by_name(env["plan"])


def test_scan_classifies(env):
    transcripts.scan([env["projects"]], env["plan"])
    items = items_by_name(env["plan"])
    assert items["2026-10-01-120000-debug-session.md"]["action"] == "decide"
    assert items["rollout-abc.jsonl"]["action"] == "decide"
    assert items["tracked-chat.md"]["action"] == "keep" and items["tracked-chat.md"]["tracked"]
    assert items["2026-11-12-100000-live.md"]["action"] == "keep"
    assert "notes.md" not in items
    assert "ingest_redacted_full" not in items["rollout-abc.jsonl"]["options"], "full ingest is opt-in"


def test_describe_redacts_and_cleans_agent_output(env):
    transcripts.scan([env["projects"]], env["plan"])
    result = transcripts.describe(env["plan"], env["staging"], swarm_arg=None)
    assert result["described"] == 2
    staged = "".join(p.read_text(encoding="utf-8") for p in env["staging"].glob("*.md"))
    plan_text = env["plan"].read_text(encoding="utf-8")
    payload = json.dumps(transcripts.jev(env["plan"]))
    for blob in (staged, plan_text, payload):
        for secret in (TOKEN, PEM_BODY, PASSWORD, RANDOM, EMAIL):
            assert secret not in blob
    assert str(Path.home()) not in staged + payload
    states = transcripts.jev(env["plan"])["state"]["items"]
    assert len(states) == 2 and all(s["description"].startswith("describes ") for s in states.values())


def _decide(env, choices: dict[str, str]):
    items = items_by_name(env["plan"])
    answers = {items[name]["id"]: {"choice": choice, "confidence": 0.9} for name, choice in choices.items()}
    path = env["root"] / "scratch" / "answers.json"
    path.write_text(json.dumps({"answers": answers}), encoding="utf-8")
    transcripts.decide_cmd(env["plan"], path, 0.5)


def test_apply_verify_restore_purge(env):
    transcripts.scan([env["projects"]], env["plan"])
    transcripts.describe(env["plan"], env["staging"], swarm_arg=None)
    _decide(env, {"2026-10-01-120000-debug-session.md": "ingest_summary", "rollout-abc.jsonl": "discard"})
    dry = transcripts.apply(env["plan"], env["service"])
    assert (
        dry["dry_run"]
        and env["session"].exists()
        and not (env["root"] / "wiki" / "notes" / "_local" / "session-archives").exists()
    )

    result = transcripts.apply(env["plan"], env["service"], do=True, backup_name="hk-test")
    assert result["transcripts"] == 2
    assert not env["session"].exists() and not env["rollout"].exists()
    quarantine = env["projects"] / "_backup" / "hk-test" / "transcripts" / "app"
    assert (quarantine / env["session"].name).exists() and (quarantine / env["rollout"].name).exists()
    notes = list((env["root"] / "wiki" / "notes" / "_local" / "session-archives" / "app").glob("*.md"))
    assert len(notes) == 1
    note = notes[0].read_text(encoding="utf-8")
    assert note.startswith("---\ntype: Report") and "pinning the clock" in note
    with env["service"].store.reader() as con:
        rows = con.execute("SELECT extracted_text, content_path FROM source_revisions").fetchall()
    stored = "".join((row["extracted_text"] or "") for row in rows)
    objects = "".join(
        (env["service"].config.data_dir / row["content_path"]).read_text(encoding="utf-8") for row in rows
    )
    for blob in (note, stored, objects):
        for secret in (TOKEN, PEM_BODY, PASSWORD, RANDOM, EMAIL):
            assert secret not in blob

    manifest = Path(result["manifest"])
    assert transcripts.verify(manifest, env["service"])["ok"]
    assert len(transcripts.restore(manifest)["commands"]) == 2
    with pytest.raises(HousekeepExit) as missing:
        transcripts.purge(manifest, env["service"], approve="", approval_note="")
    assert missing.value.code == 2
    session_id = items_by_name(env["plan"])[env["session"].name]["id"]
    preview = transcripts.purge(manifest, env["service"], approve=session_id, approval_note="ok")
    assert preview["dry_run"] and (quarantine / env["session"].name).exists()
    transcripts.purge(manifest, env["service"], approve=session_id, approval_note="delete it", do=True)
    assert not (quarantine / env["session"].name).exists() and (quarantine / env["rollout"].name).exists()
    assert transcripts.verify(manifest, env["service"])["ok"]


def test_changed_file_is_skipped(env):
    transcripts.scan([env["projects"]], env["plan"])
    transcripts.describe(env["plan"], env["staging"], swarm_arg=None)
    _decide(env, {"rollout-abc.jsonl": "discard"})
    env["rollout"].write_text("changed after the scan", encoding="utf-8")
    with pytest.raises(HousekeepExit) as failed:
        transcripts.apply(env["plan"], env["service"], do=True, backup_name="hk-test")
    assert failed.value.code == 1
    assert env["rollout"].exists()


def test_describe_without_swarm_exits_3(env):
    os.environ.pop("HK_SWARM_CMD", None)
    transcripts.scan([env["projects"]], env["plan"])
    with pytest.raises(HousekeepExit) as missing:
        transcripts.describe(env["plan"], env["staging"], swarm_arg=None)
    assert missing.value.code == 3


def test_cli_scan_and_jev(env, capsys):
    root = str(env["root"])
    assert (
        cli_main(
            [
                "--root",
                root,
                "housekeep",
                "transcripts",
                "scan",
                "--scan-root",
                str(env["projects"]),
                "--out",
                str(env["plan"]),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert cli_main(["--root", root, "--json", "housekeep", "transcripts", "jev", "--plan", str(env["plan"])]) == 0
    payload = json.loads(capsys.readouterr().out)["result"]
    assert set(payload) == {"state", "questions"} and len(payload["questions"]) == 2
