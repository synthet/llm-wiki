"""Deterministic local document-tree construction and lexical traversal."""

from __future__ import annotations

import re
import sqlite3
import uuid
from dataclasses import dataclass
from typing import Any

from .domain import canonical_json, digest_text

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
TOKEN_RE = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class Node:
    id: str
    parent_id: str | None
    depth: int
    document_order: int
    heading: str
    locator: dict[str, Any]
    content_digest: str
    token_estimate: int


def build_text_nodes(revision_id: str, text: str, markdown: bool) -> list[Node]:
    if not text:
        return []
    headings = _heading_specs(text, markdown)
    nodes: list[Node] = []
    root_locator = text_locator(text, 0, len(text))
    root = _node(revision_id, None, 0, 0, "Document", root_locator, text)
    nodes.append(root)
    order = 1
    stack: list[tuple[int, str]] = [(0, root.id)]
    sections: list[tuple[int, int, int, str, str]] = []
    for index, (heading_start, heading_end, level, title) in enumerate(headings):
        end = len(text)
        for later_start, _, later_level, _ in headings[index + 1 :]:
            if later_level <= level:
                end = later_start
                break
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent = stack[-1][1] if stack else root.id
        locator = text_locator(text, heading_start, end)
        node = _node(revision_id, parent, level, order, title, locator, text)
        nodes.append(node)
        stack.append((level, node.id))
        body_end = headings[index + 1][0] if index + 1 < len(headings) else end
        sections.append((heading_end, body_end, level, node.id, title))
        order += 1
    if not sections:
        sections = [(0, len(text), 0, root.id, "Document")]
    for start, end, level, parent_id, heading in sections:
        region = text[start:end]
        for para_match in re.finditer(r"\S(?:.|\n)*?(?=\n\s*\n|\Z)", region):
            para_start = start + para_match.start()
            para_end = start + para_match.end()
            body = text[para_start:para_end].strip()
            if not body or (markdown and HEADING_RE.fullmatch(body)):
                continue
            left_trim = len(text[para_start:para_end]) - len(text[para_start:para_end].lstrip())
            right_trim = len(text[para_start:para_end].rstrip())
            para_start += left_trim
            para_end = para_start - left_trim + right_trim
            locator = text_locator(text, para_start, para_end)
            label = _paragraph_label(body, heading)
            nodes.append(_node(revision_id, parent_id, level + 1, order, label, locator, text))
            order += 1
    return nodes


def _heading_specs(text: str, markdown: bool) -> list[tuple[int, int, int, str]]:
    if markdown:
        return [
            (match.start(), match.end(), len(match.group(1)), match.group(2).strip())
            for match in HEADING_RE.finditer(text)
        ]
    lines = text.splitlines(keepends=True)
    offsets: list[int] = []
    offset = 0
    for line in lines:
        offsets.append(offset)
        offset += len(line)
    headings: list[tuple[int, int, int, str]] = []
    index = 0
    while index < len(lines):
        title = lines[index].strip()
        underline = lines[index + 1].strip() if index + 1 < len(lines) else ""
        if title and len(title) <= 80 and underline and set(underline) <= {"="}:
            headings.append((offsets[index], offsets[index + 1] + len(lines[index + 1].rstrip()), 1, title))
            index += 2
            continue
        if title and len(title) <= 80 and underline and set(underline) <= {"-"}:
            headings.append((offsets[index], offsets[index + 1] + len(lines[index + 1].rstrip()), 2, title))
            index += 2
            continue
        letters = [char for char in title if char.isalpha()]
        if 4 <= len(title) <= 80 and letters and all(char.isupper() for char in letters):
            headings.append((offsets[index], offsets[index] + len(lines[index].rstrip()), 1, title))
        index += 1
    return headings


def build_pdf_nodes(revision_id: str, pages: list[str], outlines: list[dict[str, Any]] | None = None) -> list[Node]:
    nodes: list[Node] = []
    order = 0
    outline_labels = {int(item["page"]): str(item["title"]) for item in outlines or [] if item.get("page")}
    for page_number, page_text in enumerate(pages, 1):
        if not page_text:
            continue
        page_locator = {"kind": "pdf", "page": page_number, "char_start": 0, "char_end": len(page_text)}
        label = outline_labels.get(page_number, f"Page {page_number}")
        page_node = _node(revision_id, None, 0, order, label, page_locator, page_text)
        nodes.append(page_node)
        order += 1
        for match in re.finditer(r"\S(?:.|\n)*?(?=\n\s*\n|\Z)", page_text):
            start, end = match.span()
            fragment = page_text[start:end].strip()
            if not fragment:
                continue
            left_trim = len(page_text[start:end]) - len(page_text[start:end].lstrip())
            right_trim = len(page_text[start:end].rstrip())
            start += left_trim
            end = start - left_trim + right_trim
            locator = {"kind": "pdf", "page": page_number, "char_start": start, "char_end": end}
            nodes.append(
                _node(revision_id, page_node.id, 1, order, _paragraph_label(fragment, label), locator, page_text)
            )
            order += 1
    return nodes


def persist_nodes(con: sqlite3.Connection, revision_id: str, nodes: list[Node]) -> None:
    con.execute("DELETE FROM document_nodes WHERE source_revision_id=?", (revision_id,))
    con.executemany(
        """INSERT INTO document_nodes(
            id, source_revision_id, parent_id, depth, document_order, heading, summary,
            locator_json, content_digest, token_estimate)
            VALUES(?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)""",
        [
            (
                node.id,
                revision_id,
                node.parent_id,
                node.depth,
                node.document_order,
                node.heading,
                canonical_json(node.locator),
                node.content_digest,
                node.token_estimate,
            )
            for node in nodes
        ],
    )


def text_locator(text: str, start: int, end: int) -> dict[str, int | str]:
    return {
        "kind": "text",
        "line_start": text.count("\n", 0, start) + 1,
        "line_end": text.count("\n", 0, max(start, end - 1)) + 1,
        "char_start": start,
        "char_end": end,
    }


def _node(
    revision_id: str,
    parent_id: str | None,
    depth: int,
    order: int,
    heading: str,
    locator: dict[str, Any],
    source_text: str,
) -> Node:
    if locator["kind"] == "pdf":
        content = source_text[int(locator["char_start"]) : int(locator["char_end"])]
    else:
        content = source_text[int(locator["char_start"]) : int(locator["char_end"])]
    identity = canonical_json({"locator": locator, "heading": heading, "digest": digest_text(content)})
    return Node(
        id=str(uuid.uuid5(uuid.UUID(revision_id), identity)),
        parent_id=parent_id,
        depth=depth,
        document_order=order,
        heading=heading,
        locator=locator,
        content_digest=digest_text(content),
        token_estimate=max(1, len(TOKEN_RE.findall(content))),
    )


def _paragraph_label(fragment: str, parent_heading: str) -> str:
    first = " ".join(fragment.split())
    return first[:72] + ("…" if len(first) > 72 else "") if first else parent_heading
