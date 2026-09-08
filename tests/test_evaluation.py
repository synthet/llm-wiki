from __future__ import annotations

import json
from pathlib import Path

from conftest import proposal

from llmwiki.service import WikiService


def test_deterministic_evaluation_thresholds(tmp_path: Path):
    corpus = json.loads(Path("evals/llmwiki-corpus.json").read_text(encoding="utf-8"))
    WikiService.init(tmp_path)
    service = WikiService(tmp_path)
    records = []
    for item in corpus["sources"]:
        path = tmp_path / item["name"]
        path.write_text(item["text"], encoding="utf-8")
        ingestion = service.ingest_file(path)
        request = service.compile_export([ingestion["revision_id"]])
        leaf = next(node for node in request["evidence_bundle"] if item["claim"] in node["text"])
        result = proposal(request, leaf, entity=item["entity"], text=item["claim"])
        if records:
            result["claims"][0]["contradicts_claim_revision_ids"] = [records[0]["claim_id"]]
        claim_id = service.compile_apply(result)["claim_revision_ids"][0]
        records.append({"path": path, "ingestion": ingestion, "leaf": leaf, "claim_id": claim_id})

    candidate_answer = service.ask("Ravens memory")
    review_leakage = float(candidate_answer["insufficient"])
    for record in records:
        service.review(record["claim_id"], "approve", reviewer="Evaluator", note="Fixture evidence exact")
    answer = service.ask("Ravens memory")
    citation_coverage = sum(bool(item["evidence"]) for item in answer["citations"]) / len(answer["citations"])
    locator_validity = float(service.validate()["ok"])
    contradiction_retention = float(service.stats()["contradictions"] == 1)
    first_render = service.render()
    second_render = service.render()
    deterministic_rebuild = float(bool(first_render["rendered"]) and bool(second_render["unchanged"]))

    records[0]["path"].write_text("# Ravens\n\nRavens distinguish individual faces.\n", encoding="utf-8")
    service.ingest_file(records[0]["path"])
    first_status = service.get_claim_revision(records[0]["claim_id"])["status"]
    second_status = service.get_claim_revision(records[1]["claim_id"])["status"]
    scores = {
        "citation_coverage": citation_coverage,
        "locator_validity": locator_validity,
        "contradiction_retention": contradiction_retention,
        "review_leakage_prevention": review_leakage,
        "targeted_stale_propagation": float(first_status == "stale"),
        "unrelated_claim_stability": float(second_status == "reviewed"),
        "deterministic_rebuild": deterministic_rebuild,
    }
    assert all(scores[name] >= threshold for name, threshold in corpus["thresholds"].items()), scores
