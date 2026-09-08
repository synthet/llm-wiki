from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from llmwiki.service import WikiService


@pytest.fixture
def wiki(tmp_path: Path) -> tuple[Path, WikiService]:
    WikiService.init(tmp_path)
    return tmp_path, WikiService(tmp_path)


def ingest_and_request(root: Path, service: WikiService, text: str = "# Birds\n\nRavens remember human faces.\n"):
    source = root / "source.md"
    source.write_text(text, encoding="utf-8")
    ingestion = service.ingest_file(source)
    request = service.compile_export([ingestion["revision_id"]])
    leaf = next(node for node in request["evidence_bundle"] if "Ravens" in node["text"])
    return source, ingestion, request, leaf


def proposal(
    request: dict[str, Any],
    leaf: dict[str, Any],
    *,
    entity: str = "Raven",
    text: str = "Ravens remember human faces.",
) -> dict[str, Any]:
    return {
        "version": 1,
        "run_id": request["run_id"],
        "state_version": request["state_version"],
        "claims": [
            {
                "entity": {"name": entity},
                "text": text,
                "evidence": [
                    {
                        "source_revision_id": leaf["source_revision_id"],
                        "locator": leaf["locator"],
                        "quote": leaf["text"],
                    }
                ],
                "contradicts_claim_revision_ids": [],
            }
        ],
    }


def unwrap_tool(result: Any) -> dict[str, Any]:
    value = result.structured_content
    if isinstance(value, dict) and set(value) == {"result"}:
        value = value["result"]
    if isinstance(value, str):
        value = json.loads(value)
    assert isinstance(value, dict)
    return value
