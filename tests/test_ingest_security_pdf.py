from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfWriter

from llmwiki.errors import LLMWikiError
from llmwiki.service import WikiService


def test_path_outside_allowed_root_and_symlink_escape(wiki, tmp_path: Path):
    root, service = wiki
    outside = tmp_path.parent / "outside-source.txt"
    outside.write_text("outside", encoding="utf-8")
    with pytest.raises(LLMWikiError) as caught:
        service.ingest_file(outside)
    assert caught.value.code == "path_outside_allowed_roots"
    link = root / "link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable on this platform")
    with pytest.raises(LLMWikiError):
        service.ingest_file(link)


def test_content_signature_beats_extension_and_invalid_pdf(wiki):
    root, service = wiki
    text_named_pdf = root / "fake.pdf"
    text_named_pdf.write_text("plain UTF-8 text", encoding="utf-8")
    assert service.ingest_file(text_named_pdf)["status"] == "ready"
    broken = root / "broken.pdf"
    broken.write_bytes(b"%PDF-1.7\nnot a pdf")
    with pytest.raises(LLMWikiError) as caught:
        service.ingest_file(broken)
    assert caught.value.code == "invalid_pdf"


def test_image_only_or_blank_pdf_returns_ocr_required(wiki):
    root, service = wiki
    path = root / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with path.open("wb") as stream:
        writer.write(stream)
    result = service.ingest_file(path)
    assert result["status"] == "ocr_required"
    assert result["nodes"] == 0


def test_byte_and_pdf_page_limits(wiki):
    root, _ = wiki
    config_path = root / ".llmwiki" / "config.yaml"
    config_path.write_text(
        "version: 1\nallowed_roots: ['.']\nlimits:\n  max_bytes: 16\n  max_pdf_pages: 1\n",
        encoding="utf-8",
    )
    service = WikiService(root)
    large = root / "large.txt"
    large.write_text("x" * 17, encoding="utf-8")
    with pytest.raises(LLMWikiError) as caught:
        service.ingest_file(large)
    assert caught.value.code == "source_too_large"

    config_path.write_text(
        "version: 1\nallowed_roots: ['.']\nlimits:\n  max_bytes: 100000\n  max_pdf_pages: 1\n",
        encoding="utf-8",
    )
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_blank_page(width=100, height=100)
    pdf = root / "two-pages.pdf"
    with pdf.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(LLMWikiError) as caught:
        WikiService(root).ingest_file(pdf)
    assert caught.value.code == "pdf_page_limit"


@pytest.mark.parametrize("url", ["http://127.0.0.1/x", "http://169.254.169.254/latest/meta-data", "file:///etc/passwd"])
def test_ssrf_destinations_are_blocked(wiki, url):
    _, service = wiki
    with pytest.raises(LLMWikiError) as caught:
        service.ingest_url(url)
    assert caught.value.code in {"ssrf_blocked", "invalid_url"}
