from __future__ import annotations

import json
from pathlib import Path

from conftest import ingest_and_request, proposal

from llmwiki.cli import main


def test_tree_is_deterministic_bounded_and_revision_isolated(wiki):
    root, service = wiki
    source = root / "source.md"
    source.write_text("# One\n\nFirst fact.\n\n## Two\n\nSecond fact.\n", encoding="utf-8")
    first = service.ingest_file(source)
    nodes_first = service.list_nodes(first["revision_id"], limit=100)["items"]
    service.rebuild_index()
    nodes_again = service.list_nodes(first["revision_id"], limit=100)["items"]
    assert nodes_first == nodes_again
    assert all(node["token_estimate"] > 0 for node in nodes_first)
    source.write_text("# One\n\nChanged fact.\n", encoding="utf-8")
    second = service.ingest_file(source)
    assert service.list_nodes(first["revision_id"], limit=100)["items"] == nodes_first
    assert service.list_nodes(second["revision_id"], limit=100)["items"] != nodes_first
    result = service.search("Changed", include_nodes=True)
    assert result["backend"] in {"sqlite-fts5", "python-lexical"}
    assert result["trace_id"]
    assert len(result["nodes"]) <= 20


def test_structured_insufficiency_and_review_leakage(wiki):
    root, service = wiki
    _, _, request, leaf = ingest_and_request(root, service)
    service.compile_apply(proposal(request, leaf, text="A private candidate fact."))
    answer = service.ask("private candidate")
    assert answer["insufficient"] is True
    explicit = service.search("private candidate", statuses=["candidate"])
    assert explicit["results"][0]["status"] == "candidate"


def test_lexical_fallback_is_identified(wiki, monkeypatch):
    root, service = wiki
    _, _, request, leaf = ingest_and_request(root, service)
    claim = service.compile_apply(proposal(request, leaf))["claim_revision_ids"][0]
    service.review(claim, "approve", reviewer="R", note="Checked")
    monkeypatch.setattr(service, "_ensure_index", lambda con: "python-lexical")
    result = service.search("faces")
    assert result["backend"] == "python-lexical"
    assert result["results"]


def test_idempotent_jobs_and_cancel(wiki):
    root, service = wiki
    source = root / "job.txt"
    source.write_text("Job source", encoding="utf-8")
    first = service.submit_job("ingest_file", {"path": str(source)}, idempotency_key="same", wait=False)
    second = service.submit_job("ingest_file", {"path": str(source)}, idempotency_key="same", wait=False)
    assert first["id"] == second["id"]
    cancelled = service.cancel_job(first["id"])
    assert cancelled["status"] == "cancelled"


def test_cli_json_root_anywhere_and_exit_codes(tmp_path: Path, capsys):
    assert main(["init", "--root", str(tmp_path), "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True
    source = tmp_path / "cli.txt"
    source.write_text("CLI evidence", encoding="utf-8")
    assert main(["ingest", str(source), "--root", str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["result"]["status"] == "completed"
    assert main(["get", "missing", "--root", str(tmp_path), "--json"]) == 4
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "page_not_found"


def test_no_pageindex_dependency_or_name_in_manifest():
    manifest = Path("pyproject.toml").read_text(encoding="utf-8").casefold()
    lock = Path("uv.lock").read_text(encoding="utf-8").casefold()
    assert "pageindex" not in manifest
    assert "pageindex" not in lock
