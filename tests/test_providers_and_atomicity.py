from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from llmwiki.errors import LLMWikiError
from llmwiki.providers import OpenAICompatibleProvider, ProviderConfig
from llmwiki.service import WikiService


class FakeClient:
    responses: list[httpx.Response] = []
    calls = 0

    def __init__(self, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def post(self, *args, **kwargs):
        type(self).calls += 1
        return type(self).responses.pop(0)


def _response(status: int, payload: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status,
        json=payload or {"error": "failure"},
        request=httpx.Request("POST", "https://provider.example/v1/chat/completions"),
    )


def _provider(**overrides):
    values = {
        "mode": "api",
        "endpoint": "https://provider.example/v1",
        "compiler_model": "fixture-model",
        "retries": 2,
    }
    values.update(overrides)
    return OpenAICompatibleProvider(ProviderConfig(**values))


def test_provider_retries_only_transient_failures(monkeypatch):
    FakeClient.calls = 0
    FakeClient.responses = [
        _response(503),
        _response(
            200,
            {
                "choices": [{"message": {"content": json.dumps({"version": 1})}}],
                "usage": {"total_tokens": 10},
            },
        ),
    ]
    monkeypatch.setattr("llmwiki.providers.httpx.Client", FakeClient)
    result, usage = _provider().compile({"expected_response_schema": {}})
    assert result == {"version": 1}
    assert usage == {"total_tokens": 10}
    assert FakeClient.calls == 2


def test_provider_permanent_failure_is_not_retried(monkeypatch):
    FakeClient.calls = 0
    FakeClient.responses = [_response(400)]
    monkeypatch.setattr("llmwiki.providers.httpx.Client", FakeClient)
    with pytest.raises(LLMWikiError) as caught:
        _provider().compile({"expected_response_schema": {}})
    assert caught.value.code == "invalid_provider_response"
    assert FakeClient.calls == 1


def test_provider_request_and_token_budgets(monkeypatch):
    with pytest.raises(LLMWikiError) as caught:
        _provider(max_request_bytes=10).compile({"large": "x" * 100})
    assert caught.value.code == "provider_request_too_large"
    FakeClient.responses = [
        _response(
            200,
            {
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"total_tokens": 20},
            },
        )
    ]
    monkeypatch.setattr("llmwiki.providers.httpx.Client", FakeClient)
    with pytest.raises(LLMWikiError) as caught:
        _provider(max_tokens=10).compile({})
    assert caught.value.code == "provider_token_budget"


def test_interrupted_ingestion_rolls_back_canonical_records(tmp_path: Path, monkeypatch):
    WikiService.init(tmp_path)
    source = tmp_path / "source.txt"
    source.write_text("atomic", encoding="utf-8")
    service = WikiService(tmp_path)

    def interrupt(*args, **kwargs):
        raise RuntimeError("interrupted")

    monkeypatch.setattr("llmwiki.service.persist_nodes", interrupt)
    with pytest.raises(RuntimeError, match="interrupted"):
        service.ingest_file(source)
    assert service.stats()["sources"] == 0
    assert service.stats()["source_revisions"] == 0
