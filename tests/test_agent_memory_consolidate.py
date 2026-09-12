from __future__ import annotations

from datetime import UTC, datetime, timedelta
from os import utime
from pathlib import Path

from scripts.agent_memory import yaml_compat as yaml
from scripts.agent_memory.consolidate import (
    MemoryItem,
    find_stale_items,
    merge_sections,
    parse_front_matter,
    parse_memory_markdown,
    promote_dream,
    run_dream,
)


def _session(timestamp: str, **candidate: object) -> dict[str, object]:
    return {
        "timestamp": timestamp,
        "memory_candidates": [
            {
                "text": "Keep the durable rule.",
                "category": "working_rule",
                "confidence": "high",
                **candidate,
            }
        ],
    }


def _write_session(root: Path, name: str, data: dict[str, object]) -> None:
    raw = root / ".agent-memory" / "raw-sessions"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / name).write_text(yaml.safe_dump(data), encoding="utf-8")


def test_run_dream_promotion_consumes_sessions_without_refreshing_dates(tmp_path: Path) -> None:
    _write_session(tmp_path, "session-a.yaml", _session("2026-01-02T12:00:00Z"))

    first_dream, _ = run_dream(tmp_path)
    promote_dream(tmp_path, first_dream)
    promoted = (tmp_path / ".agent-memory" / "memory.md").read_text(encoding="utf-8")
    second_dream, _ = run_dream(tmp_path)
    dreamed_again = second_dream.read_text(encoding="utf-8")

    promoted_item = parse_memory_markdown(promoted)["Working Rules"][0]
    replayed_item = parse_memory_markdown(dreamed_again)["Working Rules"][0]
    assert promoted_item.last_updated_at == "2026-01-02"
    assert promoted_item.observed_at == "2026-01-02"
    assert promoted_item.verification_status == "unverified"
    assert promoted_item.verified_at == ""
    assert parse_front_matter(promoted)["consumed_sessions"] == ["session-a.yaml"]
    assert parse_front_matter(dreamed_again)["source_sessions"] == []
    assert replayed_item.last_updated_at == "2026-01-02"


def test_run_dream_applies_limit_after_excluding_consumed_sessions(tmp_path: Path) -> None:
    _write_session(tmp_path, "session-a.yaml", _session("2026-01-02T12:00:00Z"))
    first_dream, _ = run_dream(tmp_path)
    promote_dream(tmp_path, first_dream)

    _write_session(tmp_path, "session-b.yaml", _session("2026-02-03T09:00:00Z"))
    raw = tmp_path / ".agent-memory" / "raw-sessions"
    utime(raw / "session-b.yaml", (1, 1))
    dream, _ = run_dream(tmp_path, max_sessions=1)

    assert parse_front_matter(dream.read_text(encoding="utf-8"))["source_sessions"] == ["session-b.yaml"]


def test_merge_sections_only_new_observation_updates_dates_and_keeps_unverified() -> None:
    base = {
        section: []
        for section in (
            "Stable Project Facts",
            "User Preferences",
            "Working Rules",
            "Recurring Issues",
            "Successful Patterns",
            "Open Questions",
            "Deprecated / Superseded",
        )
    }
    first = _session("2026-01-02T12:00:00Z")
    merged, _ = merge_sections(base, [("session-a.yaml", first)], max_per_section=20)
    replayed, _ = merge_sections(merged, [("session-a.yaml", first)], max_per_section=20)
    updated, _ = merge_sections(
        replayed,
        [("session-b.yaml", _session("2026-02-03T09:00:00Z"))],
        max_per_section=20,
    )

    replayed_item = replayed["Working Rules"][0]
    updated_item = updated["Working Rules"][0]
    assert replayed_item.last_updated_at == "2026-01-02"
    assert replayed_item.verification_status == "unverified"
    assert replayed_item.verified_at == ""
    assert updated_item.observed_at == "2026-02-03"
    assert updated_item.last_updated_at == "2026-02-03"
    assert updated_item.sources == ["session-a.yaml", "session-b.yaml"]


def test_find_stale_items_explicit_stale_after_takes_precedence() -> None:
    future_update = (datetime.now(UTC).date() + timedelta(days=30)).isoformat()
    yesterday = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    sections = {
        "Working Rules": [
            MemoryItem(
                "Review this rule.",
                "Working Rules",
                last_updated_at=future_update,
                stale_after=yesterday,
            )
        ]
    }

    assert find_stale_items(sections, staleness_days=180) == [
        f"Review this rule. (stale after: {yesterday}) [section: Working Rules]"
    ]
