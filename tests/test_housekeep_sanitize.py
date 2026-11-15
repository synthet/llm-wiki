"""`llmwiki housekeep sanitize`: detection, scan scope, describe, apply, verify, restore, purge."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from llmwiki.cli import main as cli_main
from llmwiki.housekeep import detect, sanitize
from llmwiki.housekeep.common import HousekeepExit
from llmwiki.service import WikiService

TOKEN = "ghp_" + "Zq9" * 13
PEM_BODY = "MIIEowIBAAKCAQEAq7Lr0Qw9" + "Kp3x" * 10
PEM_BEGIN, PEM_END = "-----BEGIN RSA " + "PRIVATE KEY-----", "-----END RSA " + "PRIVATE KEY-----"
HEX = "0123456789abcdef" * 2 + "01234567"
RANDOM = "Qm7Zr2Lx9Pw4Kd8Vt1Bn6Hy3Jc5Gf0Sa"
EMAIL = "someone.private@mailhost.org"
OLD = time.time() - 60 * 86400

# Every secret shape the transcripts reviews reported, as (line, value that must never appear in any output).
SHAPES = [
    (f"token {TOKEN}", TOKEN),
    (f"{PEM_BEGIN}\n{PEM_BODY}\n{PEM_END}", PEM_BODY),
    ("DB_PASSWORD=opalriver77", "opalriver77"),
    ('PASSWORD="two word pass"', "two word pass"),
    ("client_secret = opal river space", "opal river space"),
    (f"Authorization: Bearer {HEX}", HEX),
    ('Authorization: Bearer "0123456789abcdef0123"', "0123456789abcdef0123"),
    ("DB_PASS=opalpass99", "opalpass99"),
    ('{"password": "a \\"quoted\\" opalquote"}', "opalquote"),
    (f"GITHUB_TOKEN={TOKEN} DB_PASSWORD=sameline77 npm run deploy", "sameline77"),
    (f"api_key: {TOKEN}, password: opal multiword", "opal multiword"),
    (f"mail {EMAIL}", EMAIL),
    (f"blob {RANDOM}", RANDOM),
    (f"home {Path.home()}", str(Path.home())),
]
SECRET_TEXT = "\n".join(line for line, _ in SHAPES) + "\n"
VALUES = [v for _, v in SHAPES]


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def commit(repo: Path, msg: str = "c") -> None:
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", msg)


@pytest.fixture
def env(tmp_path: Path):
    WikiService.init(tmp_path)
    service = WikiService(tmp_path)
    projects = tmp_path / "projects"
    app = projects / "app"
    app.mkdir(parents=True)
    git(app, "init", "-q")
    git(app, "remote", "add", "origin", "https://github.com/acme/app.git")
    (app / "config.ini").write_text("[db]\nhost = db.internal\nDB_PASSWORD=hunter2xyz\n", encoding="utf-8")
    (app / "app.py").write_text("token = get_token()\nlocKey = 'map_object_names'\n", encoding="utf-8")
    (app / "README.md").write_text("Use scheme://user:pass@host for examples.\n", encoding="utf-8")
    (app / "package.json").write_text('{"path-key": "^3.1.0", "cursor_ide_key": "abc.de.fghijk.Lmnopq"}\n', "utf-8")
    (app / ".env.example").write_text("API_TOKEN=<your token>\n", encoding="utf-8")
    (app / "docs").mkdir()
    (app / "docs" / "setup.md").write_text(f"Clone into {Path.home()}\\Projects first.\n", encoding="utf-8")
    commit(app)
    (app / ".env").write_text("API_TOKEN=abc123secret\n", encoding="utf-8")
    notes = app / "notes"
    notes.mkdir()
    old_note = notes / "old-plan.md"
    old_note.write_text("# Old plan\nWe chose SQLite over Postgres.\n" + SECRET_TEXT, encoding="utf-8")
    fresh = notes / "fresh.md"
    fresh.write_text("# Fresh\nlive work\n", encoding="utf-8")
    chat = notes / "2026-09-01-120000-chat.md"
    chat.write_text("## User\nq\n\n## Assistant\na\n", encoding="utf-8")
    skill = app / ".claude" / "skills" / "x"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    for p in (old_note, chat, skill / "SKILL.md"):
        os.utime(p, (OLD, OLD))
    upstream = projects / "upstream"
    upstream.mkdir()
    git(upstream, "init", "-q")
    git(upstream, "remote", "add", "origin", "https://github.com/other/upstream.git")
    (upstream / "x.ini").write_text("DB_PASSWORD=hunter2xyz\n", encoding="utf-8")
    commit(upstream)
    git(app, "-c", "user.name=t", "-c", "user.email=t@t", "worktree", "add", "-q", str(projects / "app-wt"))
    stub = tmp_path / "stub_swarm.py"
    stub.write_text(
        "import json, os, sys\n"
        "req = json.load(open(sys.argv[sys.argv.index('--request') + 1], encoding='utf-8'))\n"
        "out = {}\n"
        "for f in req['files']:\n"
        f"    out[f] = {{'description': 'An old plan note.', 'summary': 'We chose SQLite. Leak {TOKEN}.'}}\n"
        "ok = [{'id': 'claude', 'ok': True, 'outcome': 'ok'}]\n"
        "print(json.dumps({'ok': True, 'harnesses': ok, 'reply': json.dumps(out)}))\n",
        encoding="utf-8",
    )
    os.environ["HK_SWARM_CMD"] = json.dumps([sys.executable, str(stub)])
    yield {"root": tmp_path, "service": service, "projects": projects, "app": app, "note": old_note,
           "plan": tmp_path / "scratch" / "plan.json", "staging": tmp_path / "scratch" / "stage"}  # fmt: skip
    os.environ.pop("HK_SWARM_CMD", None)


def scan(env, **kw):
    sanitize.scan([env["projects"]], env["plan"], owners=["acme"], **kw)
    plan = json.loads(env["plan"].read_text(encoding="utf-8"))
    return plan, {i["path"]: i for i in plan["items"]}


def test_detection_is_precise_on_tracked_source():
    assert detect.secret_findings("DB_PASSWORD=hunter2xyz\n", "a.ini") == {"secret assignment": [1]}
    for text, path in [
        ("token = get_token()\n", "a.py"),
        ("locKey = 'map_object_names'\n", "a.py"),
        ('"path-key": "^3.1.0"\n', "package.json"),
        ('"cursor_ide_key": "abc.de.fghijk.Lmnopq"\n', "x.json"),
        ("INAT_OAUTH_TOKEN_URL = 'https://example.org/x'\n", "a.py"),
        ("see scheme://user:pass@host\n", "README.md"),
        ("tokenizer: bert-base-uncased\n", "m.yaml"),
    ]:
        assert detect.secret_findings(text, path) == {}, text


def test_scan_scope_and_items(env):
    plan, items = scan(env)
    assert plan["repos"] == [str(env["app"].resolve())]
    whys = {Path(s["repo"]).name: s["why"] for s in plan["skipped_repos"]}
    assert "upstream" in whys["upstream"] and "worktree" in whys["app-wt"]
    assert items["config.ini"]["kind"] == "tracked_secret" and items["config.ini"]["findings"] == {
        "secret assignment": [3]
    }
    assert items["docs/setup.md"]["kind"] == "tracked_local"
    for clean in ("app.py", "README.md", "package.json", ".env.example"):
        assert clean not in items, clean
    assert items[".env"]["kind"] == "untracked_secret_file" and items[".env"]["options"] == ["exclude", "keep"]
    assert items["notes/old-plan.md"]["kind"] == "loose_note"
    for skipped in ("notes/fresh.md", "notes/2026-09-01-120000-chat.md", ".claude/skills/x/SKILL.md"):
        assert skipped not in items, skipped
    blob = env["plan"].read_text(encoding="utf-8")
    for value in VALUES + ["hunter2xyz", "abc123secret"]:
        assert value not in blob, value


def test_describe_and_jev_never_see_secrets(env):
    scan(env)
    sanitize.describe(env["plan"], env["staging"], swarm_arg=None)
    staged = "".join(p.read_text(encoding="utf-8") for p in env["staging"].glob("S*.md"))
    payload = json.dumps(sanitize.jev(env["plan"]))
    plan_blob = env["plan"].read_text(encoding="utf-8")
    for blob in (staged, payload, plan_blob):
        for value in VALUES + ["hunter2xyz", "abc123secret"]:
            assert value not in blob, value
    assert "config.ini" not in staged, "tracked findings never reach the describe agent"
    questions = sanitize.jev(env["plan"])["questions"]
    assert len(questions) == 2  # the loose note and the stray .env


def _decide(env, choices: dict[str, str]):
    plan = json.loads(env["plan"].read_text(encoding="utf-8"))
    by_path = {i["path"]: i["id"] for i in plan["items"]}
    answers = env["root"] / "scratch" / "answers.json"
    answers.write_text(
        json.dumps({"answers": {by_path[p]: {"choice": c, "confidence": 0.9} for p, c in choices.items()}}), "utf-8"
    )
    sanitize.decide_cmd(env["plan"], answers, 0.5)


def test_apply_wiki_full_exclude_report_verify_restore_purge(env):
    scan(env, allow_full=True)
    sanitize.describe(env["plan"], env["staging"], swarm_arg=None)
    _decide(env, {"notes/old-plan.md": "wiki_full", ".env": "exclude"})
    dry = sanitize.apply(env["plan"], env["service"])
    assert dry["dry_run"] and env["note"].exists()
    result = sanitize.apply(env["plan"], env["service"], do=True, write_redacted=True, backup_name="hk-san")
    assert not env["note"].exists()
    ignored = subprocess.run(["git", "-C", str(env["app"]), "check-ignore", "-q", ".env"])
    assert ignored.returncode == 0, "the stray .env is now ignored"
    manifest = Path(result["manifest"])
    data = json.loads(manifest.read_text(encoding="utf-8"))
    copies = [Path(r["redacted_copy"]) for r in data["report"] if r.get("redacted_copy")]
    assert copies, "a redacted copy of the flagged tracked file was written"
    assert "hunter2xyz" in (env["app"] / "config.ini").read_text(encoding="utf-8"), "the repo itself is untouched"
    notes = list((env["root"] / "wiki" / "notes" / "_local" / "audit").rglob("*.md"))
    with env["service"].store.reader() as con:
        rows = con.execute("SELECT extracted_text, content_path FROM source_revisions").fetchall()
    blobs = [p.read_text(encoding="utf-8") for p in copies + notes] + [r["extracted_text"] or "" for r in rows]
    blobs += [(env["service"].config.data_dir / r["content_path"]).read_text(encoding="utf-8") for r in rows]
    blobs.append(manifest.read_text(encoding="utf-8"))
    assert len(notes) == 1 and "SQLite" in notes[0].read_text(encoding="utf-8")
    for blob in blobs:
        for value in VALUES + ["hunter2xyz", "abc123secret"]:
            assert value not in blob, value
    assert sanitize.verify(manifest, env["service"])["ok"]
    commands = sanitize.restore(manifest)["commands"]
    assert any(c.startswith("mv ") for c in commands) and any("exclude" in c for c in commands)
    note_id = next(r["id"] for r in data["sanitize"] if r["mode"] == "wiki_full")
    assert sanitize.purge(manifest, env["service"], approve=note_id, approval_note="ok", do=True)["purged"] == [note_id]


def test_changed_note_is_skipped_and_discard_quarantines(env):
    scan(env)
    _decide(env, {"notes/old-plan.md": "discard"})
    env["note"].write_text("changed", encoding="utf-8")
    with pytest.raises(HousekeepExit) as failed:
        sanitize.apply(env["plan"], env["service"], do=True, backup_name="hk-san")
    assert failed.value.code == 1 and env["note"].exists()


def test_backup_name_and_owner_are_required(env, monkeypatch):
    scan(env)
    with pytest.raises(HousekeepExit) as bad:
        sanitize.apply(env["plan"], env["service"], do=True, backup_name="../x")
    assert bad.value.code == 2
    monkeypatch.setattr(sanitize, "run", lambda *a, **k: (1, "", "no gh"))
    with pytest.raises(HousekeepExit) as missing:
        sanitize.scan([env["projects"]], env["plan"])
    assert missing.value.code == 3


def test_cli_scan(env, capsys):
    root = str(env["root"])
    args = ["--root", root, "--json", "housekeep", "sanitize", "scan", "--scan-root", str(env["projects"]),
            "--out", str(env["plan"]), "--owner", "acme"]  # fmt: skip
    assert cli_main(args) == 0
    assert json.loads(capsys.readouterr().out)["result"]["repos"] == 1


def test_linear_on_long_runs():
    start = time.monotonic()
    for line in ("a." * 100_000, "key." * 50_000, "x" * 200_000):
        detect.secret_findings(line, "notes.txt")
        detect.local_findings(line)
    assert time.monotonic() - start < 5.0
