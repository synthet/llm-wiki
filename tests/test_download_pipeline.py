from __future__ import annotations

from pathlib import Path

from llmwiki.download_ingest import (
    collect_download_files,
    consume_download_pipeline,
)
from llmwiki.service import WikiService


def test_collect_download_files_multi_extension(tmp_path: Path):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    (downloads / "doc1.md").write_text("# Doc 1\nContent 1\n", encoding="utf-8")
    (downloads / "spec.txt").write_text("Spec content\n", encoding="utf-8")
    (downloads / "ignore.bin").write_bytes(b"\x00\x01\x02")

    files = collect_download_files([downloads], extensions=(".md", ".txt"))
    names = {f.name for f in files}
    assert names == {"doc1.md", "spec.txt"}


def test_consume_download_pipeline_end_to_end(tmp_path: Path):
    WikiService.init(tmp_path)
    downloads = tmp_path / "Downloads"
    downloads.mkdir()

    doc = downloads / "research_report.md"
    doc.write_text(
        "# Research on Local Neural Models\n\n"
        "Local neural models execute on edge GPUs for latency-critical analysis.\n",
        encoding="utf-8",
    )

    config_path = tmp_path / ".llmwiki" / "config.yaml"
    text = config_path.read_text(encoding="utf-8")
    if "allowed_roots" not in text:
        config_path.write_text(
            text + '\nallowed_roots:\n  - "."\n',
            encoding="utf-8",
        )

    # 1. Dry run
    dry_res = consume_download_pipeline(
        tmp_path,
        directories=[downloads],
        run=False,
    )
    assert dry_res["file_count"] == 1
    assert dry_res["ingestable_count"] == 1
    assert doc.exists()

    # 2. Run with compile, render, and cleanup
    run_res = consume_download_pipeline(
        tmp_path,
        directories=[downloads],
        run=True,
        auto_compile=True,
        render=True,
        cleanup=True,
    )
    assert run_res["ingested"] == 1
    assert run_res["failed"] == 0
    assert run_res["compiled_claims"] >= 1
    assert run_res["rendered_pages"] >= 1
    assert run_res["cleaned_files"] == 1
    assert not doc.exists()

    # 3. Verify in store
    service = WikiService(tmp_path)
    stats = service.stats()
    assert stats["sources"] == 1
    assert stats["claims"] >= 1
    assert (tmp_path / "wiki" / "pages").exists()
