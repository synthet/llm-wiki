from __future__ import annotations

from pathlib import Path

from llmwiki.download_ingest import (
    collect_markdown_files,
    consume_download_markdown,
    discover_download_directories,
    is_downloads_dir_name,
    plan_markdown_ingest,
)
from llmwiki.service import WikiService


def test_is_downloads_dir_name():
    assert is_downloads_dir_name("Downloads")
    assert is_downloads_dir_name("download")
    assert is_downloads_dir_name("my-downloads")
    assert not is_downloads_dir_name("docs")


def test_discover_and_collect_markdown(tmp_path: Path):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    (downloads / "a.md").write_text("# A\n", encoding="utf-8")
    (downloads / "skip.txt").write_text("x", encoding="utf-8")
    nested = downloads / "nested"
    nested.mkdir()
    (nested / "b.md").write_text("# B\n", encoding="utf-8")

    found = discover_download_directories((tmp_path,))
    assert found == [downloads.resolve()]

    flat = collect_markdown_files(found, recursive=False)
    assert {p.name for p in flat} == {"a.md"}

    deep = collect_markdown_files(found, recursive=True)
    assert {p.name for p in deep} == {"a.md", "b.md"}


def test_consume_dry_run_and_ingest(tmp_path: Path):
    WikiService.init(tmp_path)
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    report = downloads / "report.md"
    report.write_text("# Report\n\nBody.\n", encoding="utf-8")

    config_path = tmp_path / ".llmwiki" / "config.yaml"
    text = config_path.read_text(encoding="utf-8")
    if "allowed_roots" not in text:
        config_path.write_text(
            text + '\nallowed_roots:\n  - "."\n',
            encoding="utf-8",
        )

    plan = consume_download_markdown(tmp_path, run=False)
    assert plan["ingestable_count"] == 1
    assert plan["plan"][0]["ingestable"] is True

    done = consume_download_markdown(tmp_path, run=True)
    assert done["ingested"] == 1
    assert done["failed"] == 0


def test_plan_rejects_outside_allowed_roots(tmp_path: Path):
    WikiService.init(tmp_path)
    outside = tmp_path.parent / "outside.md"
    outside.write_text("# X\n", encoding="utf-8")
    config = WikiService(tmp_path).config
    plan = plan_markdown_ingest(config, [outside])
    assert plan[0].ingestable is False
