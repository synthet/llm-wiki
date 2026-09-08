from __future__ import annotations

from pathlib import Path

import pytest
from conftest import ingest_and_request, proposal

from llmwiki.errors import LLMWikiError
from llmwiki.service import WikiService


def _reviewed(service, request, leaf):
    claim_id = service.compile_apply(proposal(request, leaf))["claim_revision_ids"][0]
    service.review(claim_id, "approve", reviewer="Reviewer", note="Evidence checked")
    return claim_id


def test_render_is_deterministic_and_detects_manual_edits(wiki):
    root, service = wiki
    _, _, request, leaf = ingest_and_request(root, service)
    _reviewed(service, request, leaf)
    first = service.render()
    page = Path(service.get_page("Raven")["path"])
    original = page.read_bytes()
    second = service.render()
    assert first["rendered"] == [str(page)]
    assert second["unchanged"] == [str(page)]
    assert page.read_bytes() == original
    page.write_text(page.read_text(encoding="utf-8") + "manual edit\n", encoding="utf-8")
    with pytest.raises(LLMWikiError) as caught:
        service.render()
    assert caught.value.code == "render_conflict"


def test_versioned_json_export_restore_includes_source_bytes(wiki, tmp_path: Path):
    root, service = wiki
    _, _, request, leaf = ingest_and_request(root, service)
    _reviewed(service, request, leaf)
    backup = root / "backup.json"
    result = service.export_json(backup)
    assert result["objects"] == 1
    restored_root = tmp_path / "restored"
    WikiService.init(restored_root)
    restored = WikiService(restored_root)
    restored.import_json(backup)
    assert restored.validate()["ok"]
    assert restored.ask("remember faces")["insufficient"] is False


def test_patch_era_markdown_import_preserves_files_and_marks_candidate(wiki):
    root, service = wiki
    legacy = root / "legacy"
    legacy.mkdir()
    page = legacy / "café.md"
    original = "---\ntitle: Café\nclaims:\n  - Coffee is served here.\n---\n# Café\n"
    page.write_text(original, encoding="utf-8")
    result = service.import_markdown(legacy)
    assert result["candidate_claims_imported"] == 1
    assert page.read_text(encoding="utf-8") == original
    assert service.get_page("Café")["claims"][0]["status"] == "candidate"
    with pytest.raises(LLMWikiError) as caught:
        service.review(
            service.get_page("Café")["claims"][0]["id"],
            "approve",
            reviewer="Reviewer",
            note="No evidence",
        )
    assert caught.value.code == "review_evidence_required"


def test_unicode_and_slug_collisions_remain_distinct(wiki):
    _, service = wiki
    first = service.new_entity("A B")
    second = service.new_entity("A-B")
    unicode_entity = service.new_entity("東京 Café")
    assert first["id"] != second["id"]
    assert first["slug"] != second["slug"]
    assert "東京" in unicode_entity["slug"]


def test_ambiguous_alias_is_not_force_merged(wiki):
    _, service = wiki
    service.new_entity("Alpha", ["Shared"])
    service.new_entity("Beta", ["Shared"])
    with pytest.raises(LLMWikiError) as caught:
        service.get_page("Shared")
    assert caught.value.code == "ambiguous_entity"
