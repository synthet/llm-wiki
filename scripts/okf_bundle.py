"""Shared OKF bundle parsing and link resolution for docs/ lint tools."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import yaml

SKIP_SCHEMES = frozenset({"file", "http", "https", "mailto"})
FRONTMATTER_DELIM = "---"
LOG_FILENAME = "log.md"
PROJECT_PROFILE_FIELDS = ("type", "title", "description", "resource", "tags", "timestamp")
MAX_MARKDOWN_LINK_SPAN = 8192


class OKFDocumentError(ValueError):
    pass


class LinkOutcome(Enum):
    """The security-relevant result of resolving a Markdown link."""

    SKIPPED = "external_or_skipped"
    LOCAL = "repo_local"
    ESCAPED = "escaped_repository"


@dataclass(frozen=True)
class LinkResolution:
    outcome: LinkOutcome
    docs_relative: str | None = None
    repo_relative: str | None = None


@dataclass
class OKFDocument:
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    has_frontmatter: bool = False

    @classmethod
    def parse(cls, text: str) -> OKFDocument:
        lines = text.splitlines()
        if not lines or lines[0].strip() != FRONTMATTER_DELIM:
            return cls(frontmatter={}, body=text, has_frontmatter=False)

        end_idx = None
        for i in range(1, len(lines)):
            if lines[i].strip() == FRONTMATTER_DELIM:
                end_idx = i
                break
        if end_idx is None:
            raise OKFDocumentError("Unterminated YAML frontmatter block")

        fm_text = "\n".join(lines[1:end_idx])
        try:
            fm = yaml.safe_load(fm_text) or {}
        except yaml.YAMLError as exc:
            raise OKFDocumentError(f"Invalid YAML in frontmatter: {exc}") from exc
        if not isinstance(fm, dict):
            raise OKFDocumentError("Frontmatter must be a YAML mapping")

        body = "\n".join(lines[end_idx + 1 :])
        if body.startswith("\n"):
            body = body[1:]
        return cls(frontmatter=fm, body=body, has_frontmatter=True)


def is_excluded_path(rel_path: str, exclude_prefixes: tuple[str, ...]) -> bool:
    normalized = rel_path.replace("\\", "/")
    return any(normalized.startswith(prefix) for prefix in exclude_prefixes)


def is_concept_file(rel_path: str) -> bool:
    name = Path(rel_path).name
    return name != LOG_FILENAME


def expected_resource_paths(rel_path: str, bundle_label: str = "docs") -> set[str]:
    """Accept bare (under docs/) and labelled (docs/...) resource values."""
    posix = rel_path.replace("\\", "/")
    return {posix, f"{bundle_label}/{posix}"}


def validate_timestamp(value: Any) -> str | None:
    if value is None or value == "":
        return "timestamp is missing or empty"
    if isinstance(value, datetime):
        return None
    if not isinstance(value, str):
        return "timestamp must be a string or datetime"
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        datetime.fromisoformat(raw)
    except ValueError:
        return f"timestamp is not valid ISO-8601: {value!r}"
    return None


def resolve_internal_link(
    from_file: Path, target: str, docs_root: Path, repository_root: Path
) -> LinkResolution:
    """Resolve a link while preserving both graph and existence-check paths."""
    t = target.strip()
    if not t or t.startswith("#") or t.startswith("//"):
        return LinkResolution(LinkOutcome.SKIPPED)
    parsed = urlsplit(t)
    if parsed.scheme.lower() in SKIP_SCHEMES or parsed.netloc:
        return LinkResolution(LinkOutcome.SKIPPED)
    # Unknown URI schemes are external too; a one-character scheme is allowed so
    # Windows-like paths cannot accidentally be interpreted as repository links.
    if parsed.scheme:
        return LinkResolution(LinkOutcome.SKIPPED)
    path_part = unquote(parsed.path).strip()
    if not path_part:
        return LinkResolution(LinkOutcome.SKIPPED)

    docs_root = docs_root.resolve()
    repository_root = repository_root.resolve()
    if path_part.startswith("/"):
        rel = path_part.lstrip("/")
        candidate = (docs_root / rel).resolve()
    else:
        candidate = (from_file.resolve().parent / path_part).resolve()

    try:
        repo_relative = candidate.relative_to(repository_root).as_posix()
    except ValueError:
        return LinkResolution(LinkOutcome.ESCAPED)

    try:
        docs_relative = candidate.relative_to(docs_root).as_posix()
    except ValueError:
        docs_relative = None
    return LinkResolution(LinkOutcome.LOCAL, docs_relative, repo_relative)


def _unescape_destination(value: str) -> str:
    """Remove Markdown backslash escapes without interpreting other escapes."""
    output: list[str] = []
    escaped = False
    for char in value:
        if escaped:
            output.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        else:
            output.append(char)
    if escaped:
        output.append("\\")
    return "".join(output)


def scan_markdown_link_destinations(text: str) -> list[str]:
    """Scan inline Markdown links with a bounded candidate span."""
    destinations: list[str] = []
    length = len(text)
    i = 0
    while i < length:
        if text[i] != "[" or (i and text[i - 1] == "\\"):
            i += 1
            continue
        candidate_end = min(length, i + MAX_MARKDOWN_LINK_SPAN)
        label_end = i + 1
        while label_end < candidate_end:
            if text[label_end] == "]" and text[label_end - 1] != "\\":
                break
            label_end += 1
        opening = label_end + 1
        if opening >= candidate_end or text[opening] != "(":
            i += 1
            continue

        cursor = opening + 1
        while cursor < candidate_end and text[cursor].isspace():
            cursor += 1
        if cursor >= candidate_end:
            i += 1
            continue

        if text[cursor] == "<":
            start = cursor + 1
            cursor = start
            while cursor < candidate_end and not (
                text[cursor] == ">" and text[cursor - 1] != "\\"
            ):
                cursor += 1
            if cursor >= candidate_end:
                i = opening + 1
                continue
            destination = text[start:cursor]
            cursor += 1
        else:
            start = cursor
            depth = 0
            escaped = False
            while cursor < candidate_end:
                char = text[cursor]
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == "(":
                    depth += 1
                elif char == ")":
                    if depth == 0:
                        break
                    depth -= 1
                elif char.isspace() and depth == 0:
                    break
                cursor += 1
            destination = text[start:cursor]

        # Skip the optional title and ensure the link itself is closed. Quotes
        # suppress parentheses so titles such as "why (now)" remain well formed.
        quote: str | None = None
        escaped = False
        title_depth = 0
        while cursor < candidate_end:
            char = text[cursor]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif quote:
                if char == quote:
                    quote = None
            elif char in {'"', "'"}:
                quote = char
            elif char == "(":
                title_depth += 1
            elif char == ")":
                if title_depth == 0:
                    break
                title_depth -= 1
            cursor += 1
        if cursor < candidate_end and destination:
            destinations.append(_unescape_destination(destination))
            i = cursor + 1
        else:
            i = opening + 1
    return destinations


def collect_markdown_links(
    text: str, from_file: Path, docs_root: Path, repository_root: Path
) -> list[tuple[str, LinkResolution]]:
    return [
        (target, resolve_internal_link(from_file, target, docs_root, repository_root))
        for target in scan_markdown_link_destinations(text)
    ]
