from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from conftest import ingest_and_request, proposal

from llmwiki.errors import LLMWikiError
from llmwiki.providers import ProviderConfig
from llmwiki.service import WikiService


def test_ingest_compile_review_ask_and_exact_digest(wiki):
    root, service = wiki
    source, ingestion, request, leaf = ingest_and_request(root, service)
    assert ingestion["digest"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert ingestion["nodes"] >= 2
    applied = service.compile_apply(proposal(request, leaf))
    claim_id = applied["claim_revision_ids"][0]
    assert service.search("faces")["results"] == []
    service.review(claim_id, "approve", reviewer="Ada", note="Checked exact source text")
    answer = service.ask("Which birds remember faces?")
    assert not answer["insufficient"]
    assert answer["citations"][0]["status"] == "reviewed"
    assert answer["citations"][0]["evidence"][0]["quote"] == leaf["text"]
    assert service.validate() == {"ok": True, "issues": [], "error_count": 0}


def test_duplicate_ingestion_is_noop_and_changed_revision_is_targeted_stale(wiki):
    root, service = wiki
    source, first, request, leaf = ingest_and_request(root, service)
    claim_id = service.compile_apply(proposal(request, leaf))["claim_revision_ids"][0]
    service.review(claim_id, "approve", reviewer="Ada", note="Verified")
    duplicate = service.ingest_file(source)
    assert duplicate["reused"] is True
    assert duplicate["revision_id"] == first["revision_id"]
    source.write_text("# Birds\n\nRavens can distinguish human faces.\n", encoding="utf-8")
    changed = service.ingest_file(source)
    assert changed["revision_id"] != first["revision_id"]
    assert service.get_page("Raven")["claims"][0]["status"] == "stale"


def test_invalid_agent_result_is_atomic_and_stale_result_rejected(wiki):
    root, service = wiki
    _, _, request, leaf = ingest_and_request(root, service)
    invalid = proposal(request, leaf)
    invalid["claims"].append(json.loads(json.dumps(invalid["claims"][0])))
    invalid["claims"][1]["evidence"][0]["locator"]["char_end"] = 999999
    with pytest.raises(LLMWikiError, match="out of range"):
        service.compile_apply(invalid)
    assert service.stats()["claims"] == 0
    service.new_entity("Unrelated")
    with pytest.raises(LLMWikiError) as caught:
        service.compile_apply(proposal(request, leaf))
    assert caught.value.code == "stale_compilation_result"


def test_agent_mode_makes_zero_model_calls(wiki, monkeypatch):
    root, _ = wiki
    source = root / "offline.txt"
    source.write_text("Offline evidence only.", encoding="utf-8")

    def forbidden(*args, **kwargs):
        raise AssertionError("network client constructed")

    monkeypatch.setattr("llmwiki.providers.httpx.Client", forbidden)
    service = WikiService(root, ProviderConfig(mode="agent"))
    service.ingest_file(source)
    result = service.compile()
    assert result["status"] == "awaiting_agent_result"


def test_local_mode_rejects_remote_endpoint_and_url_ingestion(wiki):
    root, _ = wiki
    with pytest.raises(LLMWikiError) as caught:
        WikiService(root, ProviderConfig(mode="local", endpoint="https://example.com/v1", compiler_model="x"))
    assert caught.value.code == "remote_endpoint_forbidden"
    local = WikiService(root, ProviderConfig(mode="local", endpoint="http://127.0.0.1:9000/v1", compiler_model="x"))
    with pytest.raises(LLMWikiError) as caught:
        local.ingest_url("https://example.com/a.txt")
    assert caught.value.code == "network_forbidden"


def test_locator_must_match_lines_and_chars(wiki):
    root, service = wiki
    _, _, request, leaf = ingest_and_request(root, service)
    invalid = proposal(request, leaf)
    invalid["claims"][0]["evidence"][0]["locator"]["line_start"] = 1
    with pytest.raises(LLMWikiError) as caught:
        service.compile_apply(invalid)
    assert caught.value.code == "invalid_locator"


def test_schema_migration_is_idempotent_and_transaction_safe(tmp_path: Path):
    WikiService.init(tmp_path)
    service = WikiService(tmp_path)
    service.store.initialize()
    service.store.initialize()
    with sqlite3.connect(service.config.db_path) as con:
        assert con.execute("SELECT version FROM schema_migrations").fetchall() == [(1,)]


def test_incremental_duplicate_is_noop_and_supersession_preserves_history(wiki):
    root, service = wiki
    _, _, request, leaf = ingest_and_request(root, service)
    first = service.compile_apply(proposal(request, leaf))["claim_revision_ids"][0]
    service.review(first, "approve", reviewer="R", note="Verified first revision")
    duplicate_request = service.compile_export()
    duplicate_leaf = next(node for node in duplicate_request["evidence_bundle"] if "Ravens" in node["text"])
    duplicate = service.compile_apply(proposal(duplicate_request, duplicate_leaf))
    assert duplicate["count"] == 0
    assert duplicate["reused_claim_revision_ids"] == [first]
    replacement_request = service.compile_export()
    replacement_leaf = next(node for node in replacement_request["evidence_bundle"] if "Ravens" in node["text"])
    replacement = proposal(
        replacement_request,
        replacement_leaf,
        text="Ravens can remember individual human faces.",
    )
    replacement["claims"][0]["supersedes_claim_revision_id"] = first
    second = service.compile_apply(replacement)["claim_revision_ids"][0]
    assert service.get_claim_revision(first)["status"] == "superseded"
    assert service.get_claim_revision(second)["status"] == "candidate"
    history = service.review_history(first)["events"]
    assert history[0]["reviewer"] == "R"
