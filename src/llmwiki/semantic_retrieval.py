"""Optional TypeSafe (Jev) reranking and citation-support judgments for retrieval."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Protocol

from .errors import error

WORD_RE = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class RetrievalConfig:
    semantic: str = "off"
    candidate_pool_multiplier: int = 5
    max_candidate_pool: int = 50
    citation_support_threshold: float = 0.55
    lexical_blend: float = 0.25
    api_key_env: str = "JEV_TOKEN"
    timeout_seconds: float = 30.0

    def validate(self) -> None:
        if self.semantic not in {"off", "heuristic", "typesafe"}:
            raise error(
                "invalid_retrieval_config",
                "Config retrieval.semantic must be off, heuristic, or typesafe.",
            )
        if self.candidate_pool_multiplier < 1:
            raise error("invalid_retrieval_config", "retrieval.candidate_pool_multiplier must be at least 1.")
        if self.max_candidate_pool < 1:
            raise error("invalid_retrieval_config", "retrieval.max_candidate_pool must be at least 1.")
        if not 0.0 <= self.citation_support_threshold <= 1.0:
            raise error("invalid_retrieval_config", "retrieval.citation_support_threshold must be between 0 and 1.")
        if not 0.0 <= self.lexical_blend <= 1.0:
            raise error("invalid_retrieval_config", "retrieval.lexical_blend must be between 0 and 1.")
        if self.timeout_seconds <= 0:
            raise error("invalid_retrieval_config", "retrieval.timeout_seconds must be positive.")


class SemanticRetrievalClient(Protocol):
    backend: str

    def rerank_claims(self, query: str, claims: list[dict[str, Any]]) -> dict[str, float]:
        """Return semantic relevance scores keyed by claim revision id."""

    def score_citation_support(self, claim_text: str, quote: str) -> float:
        """Return support probability in [0, 1] for one claim/evidence pair."""


class OffSemanticClient:
    backend = "off"

    def rerank_claims(self, query: str, claims: list[dict[str, Any]]) -> dict[str, float]:
        del query
        return {item["id"]: float(item.get("score") or 0.0) for item in claims}

    def score_citation_support(self, claim_text: str, quote: str) -> float:
        del claim_text, quote
        return 1.0


class HeuristicSemanticClient:
    """Deterministic offline stand-in for CI and local development."""

    backend = "heuristic"

    def rerank_claims(self, query: str, claims: list[dict[str, Any]]) -> dict[str, float]:
        query_tokens = set(WORD_RE.findall(query.casefold()))
        scores: dict[str, float] = {}
        for item in claims:
            text = f"{item.get('text', '')} {item.get('entity_name') or ''}"
            doc_tokens = set(WORD_RE.findall(text.casefold()))
            if not query_tokens or not doc_tokens:
                scores[item["id"]] = 0.0
                continue
            overlap = len(query_tokens & doc_tokens)
            union = len(query_tokens | doc_tokens)
            scores[item["id"]] = overlap / union if union else 0.0
        return scores

    def score_citation_support(self, claim_text: str, quote: str) -> float:
        claim_tokens = set(WORD_RE.findall(claim_text.casefold()))
        quote_tokens = set(WORD_RE.findall(quote.casefold()))
        if not claim_tokens:
            return 0.0
        if not quote_tokens:
            return 0.0
        return len(claim_tokens & quote_tokens) / len(claim_tokens)


class TypeSafeSemanticClient:
    backend = "typesafe"

    def __init__(self, config: RetrievalConfig):
        config.validate()
        try:
            from typesafe_sdk import Noul, TypeSafeClient
        except ImportError as exc:
            raise error(
                "missing_typesafe_sdk",
                "Install the optional typesafe extra: uv sync --extra typesafe",
            ) from exc
        token = os.environ.get(config.api_key_env)
        if not token:
            raise error(
                "missing_typesafe_credential",
                "TypeSafe retrieval is configured but the API key environment variable is unset.",
                env=config.api_key_env,
            )
        self._config = config
        self._api_key = token
        self._client_cls = TypeSafeClient
        self._noul_cls = Noul

    def _client(self):
        return self._client_cls(api_key=self._api_key, timeout=self._config.timeout_seconds)

    def rerank_claims(self, query: str, claims: list[dict[str, Any]]) -> dict[str, float]:
        if not claims:
            return {}
        state: dict[str, Any] = {
            "query": query,
            "candidates": [
                {"id": item["id"], "text": item.get("text", ""), "entity_name": item.get("entity_name")}
                for item in claims
            ],
        }
        questions = {
            f"rel_{index}": self._noul_cls(
                instructions=(
                    f"Given the user `query` and candidate claim `candidates[{index}]`, "
                    "is this claim a useful direct answer to the query?"
                ),
            )
            for index in range(len(claims))
        }
        with self._client() as client:
            response = client.system_one(state=state, questions=questions)
        scores: dict[str, float] = {}
        for index, item in enumerate(claims):
            answer = response.nouls[f"rel_{index}"]
            scores[item["id"]] = float(answer.noul)
        return scores

    def score_citation_support(self, claim_text: str, quote: str) -> float:
        state = {"claim_text": claim_text, "quote": quote}
        questions = {
            "supports": self._noul_cls(
                instructions="Does `quote` substantiate or support `claim_text` as evidence?",
            ),
        }
        with self._client() as client:
            response = client.system_one(state=state, questions=questions)
        return float(response.nouls["supports"].noul)

    def score_citation_support_batch(self, pairs: list[tuple[str, str, str]]) -> dict[str, float]:
        """Score many (evidence_id, claim_text, quote) tuples in one request."""
        if not pairs:
            return {}
        state = {
            "items": [{"claim_text": claim, "quote": quote} for _, claim, quote in pairs],
        }
        questions = {
            f"sup_{index}": self._noul_cls(
                instructions=(
                    f"Does `items[{index}].quote` substantiate or support `items[{index}].claim_text`?"
                ),
            )
            for index in range(len(pairs))
        }
        with self._client() as client:
            response = client.system_one(state=state, questions=questions)
        return {pairs[index][0]: float(response.nouls[f"sup_{index}"].noul) for index in range(len(pairs))}


def build_semantic_client(config: RetrievalConfig) -> SemanticRetrievalClient:
    config.validate()
    if config.semantic == "off":
        return OffSemanticClient()
    if config.semantic == "heuristic":
        return HeuristicSemanticClient()
    return TypeSafeSemanticClient(config)


def combine_rank_scores(
    claims: list[dict[str, Any]],
    semantic_scores: dict[str, float],
    *,
    lexical_blend: float,
) -> list[dict[str, Any]]:
    if not claims:
        return []
    lexical_values = [float(item.get("score") or 0.0) for item in claims]
    max_lexical = max(lexical_values) if lexical_values else 0.0

    def lexical_norm(item: dict[str, Any]) -> float:
        raw = float(item.get("score") or 0.0)
        if max_lexical <= 0:
            return 0.0
        return raw / max_lexical

    ranked = sorted(
        claims,
        key=lambda item: (
            -(
                semantic_scores.get(item["id"], 0.0) * (1.0 - lexical_blend)
                + lexical_norm(item) * lexical_blend
            ),
            item["id"],
        ),
    )
    for item in ranked:
        item["semantic_score"] = round(semantic_scores.get(item["id"], 0.0), 6)
        item["rank_score"] = round(
            semantic_scores.get(item["id"], 0.0) * (1.0 - lexical_blend) + lexical_norm(item) * lexical_blend,
            6,
        )
    return ranked


def annotate_claim_citations(
    claims: list[dict[str, Any]],
    client: SemanticRetrievalClient,
    *,
    threshold: float,
) -> list[dict[str, Any]]:
    pairs: list[tuple[str, str, str]] = []
    for claim in claims:
        for evidence in claim.get("evidence") or []:
            pairs.append((evidence["id"], claim["text"], evidence["quote"]))

    support_by_evidence: dict[str, float] = {}
    if isinstance(client, TypeSafeSemanticClient):
        support_by_evidence = client.score_citation_support_batch(pairs)
    else:
        for evidence_id, claim_text, quote in pairs:
            support_by_evidence[evidence_id] = client.score_citation_support(claim_text, quote)

    annotated: list[dict[str, Any]] = []
    for claim in claims:
        evidence_rows = []
        best = 0.0
        for evidence in claim.get("evidence") or []:
            support = float(support_by_evidence.get(evidence["id"], 0.0))
            best = max(best, support)
            evidence_rows.append(
                {
                    **evidence,
                    "citation_support": round(support, 6),
                    "citation_supported": support >= threshold,
                }
            )
        annotated.append(
            {
                **claim,
                "evidence": evidence_rows,
                "citation_support": round(best, 6),
                "citation_supported": best >= threshold,
            }
        )
    return annotated
