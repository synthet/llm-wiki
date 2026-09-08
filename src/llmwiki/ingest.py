"""Secure acquisition and deterministic extraction for supported source types."""

from __future__ import annotations

import io
import ipaddress
import mimetypes
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from pypdf import PdfReader

from .config import WikiConfig, ensure_within
from .domain import PARSER_VERSION, TREE_FORMAT_VERSION, canonical_json, digest_bytes, digest_text
from .errors import LLMWikiError, error
from .tree import Node, build_pdf_nodes, build_text_nodes


@dataclass(frozen=True)
class Extraction:
    data: bytes
    digest: str
    media_type: str
    text: str
    metadata: dict[str, Any]
    status: str
    nodes: list[Node]


def acquire_file(path: Path, config: WikiConfig) -> tuple[bytes, str, str]:
    safe_path = ensure_within(path, config.allowed_roots)
    if not safe_path.is_file():
        raise error("source_not_file", "Source path is not a regular file.", path=str(safe_path))
    size = safe_path.stat().st_size
    if size > config.max_bytes:
        raise error("source_too_large", "Source exceeds configured byte limit.", size=size)
    data = safe_path.read_bytes()
    return data, safe_path.as_uri(), safe_path.name


def acquire_url(url: str, config: WikiConfig, *, mode: str) -> tuple[bytes, str, str, str | None]:
    if mode == "local":
        raise error("network_forbidden", "URL ingestion is disabled in local provider mode.")
    current = url
    with httpx.Client(follow_redirects=False, timeout=config.http_timeout_seconds, trust_env=False) as client:
        for _ in range(6):
            before = _validate_public_url(current)
            try:
                with client.stream("GET", current, headers={"User-Agent": "llmwiki/0.1"}) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise error("invalid_redirect", "Redirect response omitted Location.")
                        current = urljoin(current, location)
                        continue
                    response.raise_for_status()
                    after = _resolve_public(response.url.host or "")
                    if before != after:
                        raise error("dns_rebinding_detected", "URL host resolution changed during acquisition.")
                    chunks: list[bytes] = []
                    length = 0
                    for chunk in response.iter_bytes():
                        length += len(chunk)
                        if length > config.max_download_bytes:
                            raise error("download_too_large", "Download exceeds configured byte limit.")
                        chunks.append(chunk)
                    name = Path(response.url.path).name or response.url.host or "download"
                    return b"".join(chunks), str(response.url), name, response.headers.get("content-type")
            except LLMWikiError:
                raise
            except (httpx.HTTPError, OSError) as exc:
                raise error("download_failed", "URL acquisition failed.", reason=type(exc).__name__) from exc
    raise error("too_many_redirects", "URL exceeded the redirect limit.")


def extract(
    data: bytes,
    name: str,
    config: WikiConfig,
    declared_media_type: str | None = None,
) -> Extraction:
    if len(data) > config.max_bytes:
        raise error("source_too_large", "Source exceeds configured byte limit.", size=len(data))
    digest = digest_bytes(data)
    if data.startswith(b"%PDF-"):
        return _extract_pdf(data, digest, config)
    if b"\x00" in data[:4096]:
        raise error("unsupported_media_type", "Binary source is not a supported text or PDF document.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise error("invalid_utf8", "Markdown and text sources must be valid UTF-8.") from exc
    guessed = mimetypes.guess_type(name)[0]
    markdown = Path(name).suffix.lower() in {".md", ".markdown"}
    media_type = "text/markdown" if markdown else "text/plain"
    if declared_media_type and declared_media_type.split(";", 1)[0] in {"text/markdown", "text/plain"}:
        media_type = declared_media_type.split(";", 1)[0]
        markdown = media_type == "text/markdown"
    elif guessed == "text/markdown":
        media_type, markdown = "text/markdown", True
    metadata = {
        "kind": "text",
        "encoding": "utf-8",
        "line_count": len(text.splitlines()),
        "tree_format_version": TREE_FORMAT_VERSION,
    }
    return Extraction(
        data=data,
        digest=digest,
        media_type=media_type,
        text=text,
        metadata=metadata,
        status="ready",
        nodes=build_text_nodes(_temporary_revision_id(digest), text, markdown),
    )


def rebuild_node_ids(extraction: Extraction, revision_id: str) -> list[Node]:
    if extraction.metadata["kind"] == "pdf":
        return build_pdf_nodes(revision_id, extraction.metadata["pages"], extraction.metadata.get("outlines"))
    return build_text_nodes(revision_id, extraction.text, extraction.media_type == "text/markdown")


def extraction_config_digest(config: WikiConfig) -> str:
    return digest_text(
        canonical_json(
            {
                "parser": PARSER_VERSION,
                "tree": TREE_FORMAT_VERSION,
                "max_bytes": config.max_bytes,
                "max_pdf_pages": config.max_pdf_pages,
            }
        )
    )


def _extract_pdf(data: bytes, digest: str, config: WikiConfig) -> Extraction:
    started = time.monotonic()
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise error("encrypted_pdf", "Encrypted PDFs are not supported.")
        if len(reader.pages) > config.max_pdf_pages:
            raise error("pdf_page_limit", "PDF exceeds configured page limit.", pages=len(reader.pages))
        pages: list[str] = []
        for page in reader.pages:
            if time.monotonic() - started > config.parse_timeout_seconds:
                raise error("parse_timeout", "PDF parsing exceeded the configured time limit.")
            pages.append(page.extract_text() or "")
        outlines = _pdf_outlines(reader)
    except LLMWikiError:
        raise
    except Exception as exc:
        raise error("invalid_pdf", "PDF could not be parsed.", reason=type(exc).__name__) from exc
    usable = sum(len(page.strip()) for page in pages)
    status = "ready" if usable else "ocr_required"
    text = "\n\n".join(pages)
    metadata = {
        "kind": "pdf",
        "pages": pages,
        "page_count": len(pages),
        "outlines": outlines,
        "tree_format_version": TREE_FORMAT_VERSION,
    }
    return Extraction(
        data=data,
        digest=digest,
        media_type="application/pdf",
        text=text,
        metadata=metadata,
        status=status,
        nodes=[] if status == "ocr_required" else build_pdf_nodes(_temporary_revision_id(digest), pages, outlines),
    )


def _pdf_outlines(reader: PdfReader) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    def visit(items: list[Any], depth: int = 0) -> None:
        for item in items:
            if isinstance(item, list):
                visit(item, depth + 1)
                continue
            try:
                page = reader.get_destination_page_number(item) + 1
                title = str(item.title)
            except Exception:
                continue
            result.append({"title": title, "page": page, "depth": depth})

    try:
        visit(reader.outline)
    except Exception:
        return []
    return result


def _validate_public_url(url: str) -> frozenset[str]:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise error("invalid_url", "Only explicit HTTP(S) resource URLs are supported.")
    if parsed.username or parsed.password:
        raise error("invalid_url", "Credentials in source URLs are not allowed.")
    return _resolve_public(parsed.hostname)


def _resolve_public(hostname: str) -> frozenset[str]:
    try:
        records = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise error("dns_failed", "URL hostname could not be resolved.") from exc
    addresses = frozenset(record[4][0] for record in records)
    if not addresses:
        raise error("dns_failed", "URL hostname did not resolve to an address.")
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
        if not ip.is_global:
            raise error("ssrf_blocked", "URL resolves to a non-public network address.")
    return addresses


def _temporary_revision_id(digest: str) -> str:
    return str(uuid_from_digest(digest))


def uuid_from_digest(digest: str):
    import uuid

    return uuid.uuid5(uuid.NAMESPACE_URL, f"llmwiki:temporary:{digest}")
