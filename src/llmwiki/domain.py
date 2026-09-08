"""Domain constants and evidence/state validation."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from .errors import error

SCHEMA_VERSION = 1
EXPORT_VERSION = 1
AGENT_REQUEST_VERSION = 1
PARSER_VERSION = "llmwiki-parser/1"
TREE_FORMAT_VERSION = "llmwiki-tree/1"
CLAIM_STATES = {"candidate", "reviewed", "disputed", "stale", "superseded", "retracted"}
ALLOWED_TRANSITIONS = {
    "candidate": {"reviewed", "disputed", "retracted", "stale"},
    "reviewed": {"disputed", "stale", "superseded", "retracted"},
    "disputed": {"reviewed", "stale", "superseded", "retracted"},
    "stale": {"superseded", "retracted"},
    "superseded": set(),
    "retracted": set(),
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_text(value: str) -> str:
    return digest_bytes(value.encode("utf-8"))


def validate_transition(before: str, after: str) -> None:
    if before not in CLAIM_STATES or after not in CLAIM_STATES:
        raise error("invalid_claim_state", "Unknown claim state.", before=before, after=after)
    if after not in ALLOWED_TRANSITIONS[before]:
        raise error(
            "invalid_state_transition",
            f"Claim cannot transition from {before} to {after}.",
            before=before,
            after=after,
        )


def validate_locator(locator: dict[str, Any], text: str, pages: list[str] | None = None) -> str:
    kind = locator.get("kind")
    if kind == "text":
        required = ("line_start", "line_end", "char_start", "char_end")
        if any(not isinstance(locator.get(key), int) for key in required):
            raise error("invalid_locator", "Text locator fields must be integers.")
        start, end = locator["char_start"], locator["char_end"]
        line_start, line_end = locator["line_start"], locator["line_end"]
        lines = text.splitlines(keepends=True) or [""]
        if not (0 <= start < end <= len(text)):
            raise error("invalid_locator", "Text character bounds are out of range.")
        if not (1 <= line_start <= line_end <= len(lines)):
            raise error("invalid_locator", "Text line bounds are out of range.")
        actual_line_start = text.count("\n", 0, start) + 1
        actual_line_end = text.count("\n", 0, max(start, end - 1)) + 1
        if (line_start, line_end) != (actual_line_start, actual_line_end):
            raise error("invalid_locator", "Line and character bounds do not identify the same text.")
        return text[start:end]
    if kind == "pdf":
        if pages is None:
            raise error("invalid_locator", "PDF page text is unavailable.")
        page, start, end = locator.get("page"), locator.get("char_start"), locator.get("char_end")
        if not all(isinstance(value, int) for value in (page, start, end)):
            raise error("invalid_locator", "PDF locator fields must be integers.")
        if not (1 <= page <= len(pages)):
            raise error("invalid_locator", "PDF page is out of range.")
        page_text = pages[page - 1]
        if not (0 <= start < end <= len(page_text)):
            raise error("invalid_locator", "PDF character bounds are out of range.")
        return page_text[start:end]
    raise error("invalid_locator", "Locator kind must be 'text' or 'pdf'.")
