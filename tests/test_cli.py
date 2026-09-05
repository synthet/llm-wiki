import json

from llmwiki import cli


def test_cli_lint_ok(sample_wiki, capsys):
    rc = cli.main(["--root", str(sample_wiki), "lint", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["ok"] is True


def test_cli_lint_fails_on_broken(tmp_path, capsys):
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "b.md").write_text(
        "---\nid: e:b\ntitle: B\ntype: entity\nstatus: candidate\n---\n\n[[Missing]]\n",
        encoding="utf-8",
    )
    rc = cli.main(["--root", str(tmp_path), "lint"])
    assert rc == 1
    assert "broken-wikilink" in capsys.readouterr().out


def test_cli_index_and_search(sample_wiki, capsys):
    assert cli.main(["--root", str(sample_wiki), "index"]) == 0
    capsys.readouterr()
    rc = cli.main(["--root", str(sample_wiki), "search", "CKAN", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["count"] >= 1


def test_cli_new_and_stats(tmp_path, capsys):
    assert cli.main(["init", str(tmp_path)]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(tmp_path), "new", "My Topic", "--type", "topic"]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(tmp_path), "stats", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["pages"] >= 2  # index + new page


def test_cli_get_json(sample_wiki, capsys):
    rc = cli.main(["--root", str(sample_wiki), "get", "OKF", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["found"] is True
    assert out["id"] == "entity:google-okf"


def test_cli_new_page_is_lint_clean(tmp_path, capsys):
    cli.main(["init", str(tmp_path)])
    cli.main(["--root", str(tmp_path), "new", "Fresh Note"])
    capsys.readouterr()
    # A freshly scaffolded wiki + new page must be lint-clean out of the box:
    # illustrative wikilinks in the templates live inside code spans.
    rc = cli.main(["--root", str(tmp_path), "lint", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0, out["issues"]
    assert out["ok"] is True


def test_wikilinks_in_code_are_ignored(tmp_path):
    from llmwiki.model import extract_links
    body = (
        "Real [[Alpha]] link.\n"
        "Inline `[[NotALink]]` example.\n"
        "```\n[[AlsoNotALink]]\n```\n"
    )
    targets = {l.target for l in extract_links(body)}
    assert targets == {"Alpha"}
