import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from okf_bundle import LinkOutcome, collect_markdown_links, resolve_internal_link  # noqa: E402
from okf_lint import lint_bundle  # noqa: E402
from wiki_lint_scan import lint_docs  # noqa: E402


def test_resolution_distinguishes_docs_repo_external_and_escape(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    page = docs / "guide" / "page.md"
    page.parent.mkdir(parents=True)
    page.write_text("", encoding="utf-8")

    docs_link = resolve_internal_link(page, "../target.md#section", docs, repo)
    assert docs_link.outcome is LinkOutcome.LOCAL
    assert docs_link.docs_relative == "target.md"
    assert docs_link.repo_relative == "docs/target.md"

    code_link = resolve_internal_link(page, "../../src/module.py#L10", docs, repo)
    assert code_link.outcome is LinkOutcome.LOCAL
    assert code_link.docs_relative is None
    assert code_link.repo_relative == "src/module.py"

    assert resolve_internal_link(page, "https://example.com/a", docs, repo).outcome is LinkOutcome.SKIPPED
    assert resolve_internal_link(page, "#local", docs, repo).outcome is LinkOutcome.SKIPPED
    assert resolve_internal_link(page, "../../../secret", docs, repo).outcome is LinkOutcome.ESCAPED


def test_scanner_supports_markdown_destination_forms(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    page = docs / "page.md"
    docs.mkdir(parents=True)
    page.write_text("", encoding="utf-8")
    text = (
        r'[balanced](file_(one).md "title") '
        r'[escaped](file_\(two\).md) '
        r'[angle](<file (three).md> "optional title") '
        r'[external](https://example.com/a_(b))'
    )

    links = collect_markdown_links(text, page, docs, repo)

    assert [raw for raw, _ in links] == [
        "file_(one).md",
        "file_(two).md",
        "file (three).md",
        "https://example.com/a_(b)",
    ]
    assert [result.outcome for _, result in links] == [
        LinkOutcome.LOCAL,
        LinkOutcome.LOCAL,
        LinkOutcome.LOCAL,
        LinkOutcome.SKIPPED,
    ]


def test_lint_validates_cross_directory_files_directories_and_missing_targets(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    (repo / "src").mkdir()
    (repo / "src" / "present.py").write_text("", encoding="utf-8")
    (repo / ".agent").mkdir()
    (docs / "notes (draft).md").write_text("", encoding="utf-8")
    (docs / "page.md").write_text(
        "\n".join(
            [
                "[code](../src/present.py#L1)",
                "[directory](../.agent/)",
                "[parentheses](<notes (draft).md>)",
                "[missing](../scripts/missing.py)",
                "[escape](../../outside.txt)",
            ]
        ),
        encoding="utf-8",
    )

    report = lint_bundle(docs, profile="minimal", repository_root=repo)

    broken = [finding for finding in report.findings if finding.code == "broken_internal_link"]
    escaped = [finding for finding in report.findings if finding.code == "link_escapes_repository"]
    assert len(broken) == 1
    assert "scripts/missing.py" in broken[0].message
    assert len(escaped) == 1

    scan = lint_docs(docs, repo)
    assert ("page.md", "../src/present.py#L1") not in scan["broken_docs"]
    assert ("page.md", "../scripts/missing.py") in scan["broken_docs"]
