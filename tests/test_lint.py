from pathlib import Path

from llmwiki import lint
from llmwiki.wiki import Wiki


def _rules(issues):
    return {i.rule for i in issues}


def test_sample_wiki_is_clean(sample_wiki):
    wiki = Wiki(sample_wiki).load()
    issues = lint.lint(wiki, strict=True)
    assert lint.summarize(issues)["error"] == 0, [i.format() for i in issues]


def test_tmp_wiki_is_clean(tmp_wiki):
    wiki = Wiki(tmp_wiki).load()
    issues = lint.lint(wiki)
    assert lint.summarize(issues)["error"] == 0, [i.format() for i in issues]


def test_broken_wiki_detects_errors(tmp_path):
    pages = tmp_path / "pages"
    pages.mkdir()
    (tmp_path / "wiki.yaml").write_text("name: t\n", encoding="utf-8")
    # broken link, invalid status, missing evidence on reviewed claim
    (pages / "bad.md").write_text(
        "---\n"
        "id: entity:bad\ntitle: Bad\ntype: entity\nstatus: nonsense\n"
        "claims:\n  - id: claim:x\n    text: t\n    status: reviewed\n"
        "---\n\n# Bad\n\nBroken [[Does Not Exist]].\n",
        encoding="utf-8",
    )
    # duplicate id
    (pages / "dup.md").write_text(
        "---\nid: entity:bad\ntitle: Dup\ntype: entity\nstatus: candidate\n---\n\n# Dup\n",
        encoding="utf-8",
    )
    wiki = Wiki(tmp_path).load()
    issues = lint.lint(wiki, strict=True)
    rules = _rules(issues)
    assert "invalid-status" in rules
    assert "broken-wikilink" in rules
    assert "missing-evidence" in rules
    assert "duplicate-id" in rules
    assert lint.summarize(issues)["error"] > 0


def test_missing_evidence_severity_depends_on_strict(tmp_path):
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "p.md").write_text(
        "---\nid: entity:p\ntitle: P\ntype: entity\nstatus: reviewed\n"
        "claims:\n  - id: claim:c\n    text: t\n    status: reviewed\n---\n\n# P\n",
        encoding="utf-8",
    )
    wiki = Wiki(tmp_path).load()
    lenient = lint.lint(wiki, strict=False)
    strict = lint.lint(wiki, strict=True)
    assert any(i.rule == "missing-evidence" and i.severity == "warning" for i in lenient)
    assert any(i.rule == "missing-evidence" and i.severity == "error" for i in strict)


def test_malformed_frontmatter_reported(tmp_path):
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "m.md").write_text("---\nid: x\ntitle: Y\nunterminated\n", encoding="utf-8")
    wiki = Wiki(tmp_path).load()
    issues = lint.lint(wiki)
    assert any(i.rule == "frontmatter-parse" for i in issues)
