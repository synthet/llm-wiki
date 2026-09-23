from __future__ import annotations

import os
from pathlib import Path

import yaml
from conftest import ingest_and_request, proposal

from llmwiki.config import WikiConfig, load_dotenv
from llmwiki.service import WikiService


def _enable_heuristic_retrieval(root: Path) -> None:
    config_path = root / ".llmwiki" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["retrieval"] = {
        "semantic": "heuristic",
        "candidate_pool_multiplier": 5,
        "citation_support_threshold": 0.55,
        "lexical_blend": 0.1,
    }
    config_path.write_text(yaml.safe_dump(config, sort_keys=True), encoding="utf-8")


def test_load_dotenv_sets_missing_jev_token(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("JEV_TOKEN", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text('JEV_TOKEN="unit-test-placeholder"\n', encoding="utf-8")

    assert load_dotenv(env_path) == 1
    assert os.environ.get("JEV_TOKEN") == "unit-test-placeholder"
    assert load_dotenv(env_path) == 0


def test_config_defaults_to_jev_token_env_name(tmp_path: Path):
    WikiService.init(tmp_path)
    config = WikiConfig.load(tmp_path)
    assert config.retrieval.api_key_env == "JEV_TOKEN"


def test_heuristic_rerank_prefers_semantically_aligned_claim(wiki):
    root, _service = wiki
    _enable_heuristic_retrieval(root)
    service = WikiService(root)
    source = root / "animals.md"
    source.write_text(
        "# Animals\n\nRavens remember human faces.\n\nQuokkas are small marsupials.\n",
        encoding="utf-8",
    )
    ingestion = service.ingest_file(source)
    request = service.compile_export([ingestion["revision_id"]])
    raven_leaf = next(node for node in request["evidence_bundle"] if "Ravens" in node["text"])
    quokka_leaf = next(node for node in request["evidence_bundle"] if "Quokkas" in node["text"])
    combined = {
        "version": 1,
        "run_id": request["run_id"],
        "state_version": request["state_version"],
        "claims": [
            {
                "entity": {"name": "Raven"},
                "text": "Ravens remember human faces.",
                "evidence": [
                    {
                        "source_revision_id": raven_leaf["source_revision_id"],
                        "locator": raven_leaf["locator"],
                        "quote": raven_leaf["text"],
                    }
                ],
                "contradicts_claim_revision_ids": [],
            },
            {
                "entity": {"name": "Quokka"},
                "text": "Quokkas are small marsupials.",
                "evidence": [
                    {
                        "source_revision_id": quokka_leaf["source_revision_id"],
                        "locator": quokka_leaf["locator"],
                        "quote": quokka_leaf["text"],
                    }
                ],
                "contradicts_claim_revision_ids": [],
            },
        ],
    }
    raven, quokka = service.compile_apply(combined)["claim_revision_ids"]
    service.review(raven, "approve", reviewer="R", note="Checked")
    service.review(quokka, "approve", reviewer="R", note="Checked")
    service.rebuild_index()

    result = service.search("quokka marsupial", limit=1)

    assert result["semantic_backend"] == "heuristic"
    assert result["results"][0]["text"] == "Quokkas are small marsupials."
    assert result["trace"]["method"].startswith("lexical+semantic-rerank")


def test_ask_filters_unsupported_citations_with_heuristic(wiki):
    root, _service = wiki
    _enable_heuristic_retrieval(root)
    service = WikiService(root)
    _, _, request, leaf = ingest_and_request(root, service)
    claim = service.compile_apply(
        proposal(request, leaf, text="Elephants can fly long distances without rest."),
    )["claim_revision_ids"][0]
    service.review(claim, "approve", reviewer="R", note="Checked")
    service.rebuild_index()

    answer = service.ask("elephants fly")

    assert answer["semantic_backend"] == "heuristic"
    assert answer["insufficient"] is True
    assert "citation support" in answer["reason"].casefold()


def test_semantic_off_preserves_legacy_search_trace(wiki):
    root, service = wiki
    _, _, request, leaf = ingest_and_request(root, service)
    claim = service.compile_apply(proposal(request, leaf))["claim_revision_ids"][0]
    service.review(claim, "approve", reviewer="R", note="Checked")

    result = service.search("faces")

    assert result["semantic_backend"] == "off"
    assert result["trace"]["method"] == "lexical"
    assert result["results"]
