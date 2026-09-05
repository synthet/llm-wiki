import llmwiki.index as index_mod
from llmwiki import ops
from llmwiki.index import Index
from llmwiki.search import search
from llmwiki.wiki import Wiki


def test_index_and_search_fts(tmp_wiki):
    Index(tmp_wiki).build(Wiki(tmp_wiki).load())
    results = search(tmp_wiki, "beta")
    assert results, "expected at least one match"
    assert results[0].title in ("Alpha", "Beta")


def test_search_json_backend(tmp_wiki, monkeypatch):
    # Force the JSON inverted-index fallback path.
    monkeypatch.setattr(index_mod, "fts5_available", lambda: False)
    idx = Index(tmp_wiki)
    assert idx.use_fts is False
    idx.build(Wiki(tmp_wiki).load())
    assert idx.backend_name() == "json-inverted"
    results = idx.search("alpha")
    assert any(r.title == "Alpha" for r in results)


def test_search_status_filter(sample_wiki):
    Index(sample_wiki).build()
    res = ops.search(sample_wiki, "provenance", status="candidate")
    assert res["count"] >= 1
    assert all(r["status"] == "candidate" for r in res["results"])


def test_search_expand_adds_wikilinks(sample_wiki):
    Index(sample_wiki).build()
    res = ops.search(sample_wiki, "Open Knowledge Format", limit=1, expand=True)
    vias = {r["matched_via"] for r in res["results"]}
    assert "wikilink" in vias


def test_search_without_index_raises(tmp_path):
    (tmp_path / "pages").mkdir()
    idx = Index(tmp_path)
    try:
        idx.search("x")
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")
