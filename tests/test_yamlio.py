import pytest

from llmwiki import yamlio


BLOCK_DOC = """\
id: entity:x
title: X
tags: [a, b, c]
claims:
  - id: claim:1
    text: >-
      A folded scalar that spans
      several lines into one.
    status: reviewed
    confidence: 0.9
    evidence:
      - source_id: source:s
        locator: {type: document}
freshness:
  stale: false
"""


def _parse(monkeypatch, force_fallback):
    if force_fallback:
        monkeypatch.setattr(yamlio, "_yaml", None)
    return yamlio.load_yaml(BLOCK_DOC)


@pytest.mark.parametrize("force_fallback", [False, True])
def test_block_scalar_and_nesting(monkeypatch, force_fallback):
    data = _parse(monkeypatch, force_fallback)
    assert data["id"] == "entity:x"
    assert data["tags"] == ["a", "b", "c"]
    assert len(data["claims"]) == 1
    claim = data["claims"][0]
    assert claim["text"] == "A folded scalar that spans several lines into one."
    assert claim["confidence"] == 0.9
    assert claim["evidence"][0]["source_id"] == "source:s"
    assert claim["evidence"][0]["locator"] == {"type": "document"}
    assert data["freshness"]["stale"] is False


def test_split_frontmatter_roundtrip():
    fm = {"id": "page:a", "title": "A", "tags": ["one", "two"], "n": 3, "ok": True}
    body = "# A\n\nBody text.\n"
    doc = yamlio.render_page(fm, body)
    parsed, parsed_body, _ = yamlio.split_frontmatter(doc)
    assert parsed["id"] == "page:a"
    assert parsed["tags"] == ["one", "two"]
    assert parsed["n"] == 3
    assert parsed["ok"] is True
    assert "Body text." in parsed_body


def test_missing_close_raises():
    with pytest.raises(ValueError):
        yamlio.split_frontmatter("---\nid: x\nno close here\n")


def test_no_frontmatter():
    fm, body, raw = yamlio.split_frontmatter("# Just a heading\n")
    assert fm == {}
    assert body.startswith("# Just")
