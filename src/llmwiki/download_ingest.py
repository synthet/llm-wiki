"""Discover and process documents under Downloads-style directories into the wiki store."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import WikiConfig, ensure_within
from .errors import LLMWikiError
from .service import WikiService

DEFAULT_EXTENSIONS: tuple[str, ...] = (".md", ".markdown", ".txt", ".pdf")


def is_downloads_dir_name(name: str) -> bool:
    lowered = name.strip().lower()
    return lowered in {"downloads", "download"} or lowered.endswith("-downloads")


def discover_download_directories(
    allowed_roots: Iterable[Path],
    *,
    include_home_downloads: bool = True,
) -> list[Path]:
    """Return existing directories that look like a Downloads folder and are under allowed_roots."""
    roots = tuple(root.resolve() for root in allowed_roots)
    seen: set[Path] = set()
    found: list[Path] = []

    def add(path: Path) -> None:
        resolved = path.resolve()
        if not resolved.is_dir() or resolved in seen:
            return
        if not _is_under_any_allowed(resolved, roots):
            return
        seen.add(resolved)
        found.append(resolved)

    for root in roots:
        if root.is_dir() and is_downloads_dir_name(root.name):
            add(root)
        if root.is_dir():
            try:
                for child in root.iterdir():
                    if child.is_dir() and is_downloads_dir_name(child.name):
                        add(child)
            except OSError:
                continue

    if include_home_downloads:
        home = (Path.home() / "Downloads").resolve()
        if home.is_dir() and _is_under_any_allowed(home, roots):
            add(home)

    return sorted(found)


def _is_under_any_allowed(path: Path, allowed_roots: tuple[Path, ...]) -> bool:
    return any(path == root or root in path.parents for root in allowed_roots)


def collect_download_files(
    directories: Iterable[Path],
    *,
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS,
    recursive: bool = False,
    max_files: int = 200,
) -> list[Path]:
    """Collect candidate documents from directories, sorted by mtime (newest first)."""
    if max_files < 1:
        raise ValueError("max_files must be at least 1")
    exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
    paths: list[Path] = []
    for directory in directories:
        base = directory.resolve()
        if not base.is_dir():
            continue
        if recursive:
            for p in base.rglob("*"):
                if p.is_file() and p.suffix.lower() in exts:
                    paths.append(p)
        else:
            for p in base.iterdir():
                if p.is_file() and p.suffix.lower() in exts:
                    paths.append(p)

    unique = {p.resolve(): p.resolve() for p in paths if p.is_file()}
    ordered = sorted(unique.values(), key=lambda p: p.stat().st_mtime, reverse=True)
    return ordered[:max_files]


def collect_markdown_files(
    directories: Iterable[Path],
    *,
    recursive: bool = False,
    max_files: int = 200,
) -> list[Path]:
    """Legacy helper: collect `.md` / `.markdown` files from directories."""
    return collect_download_files(
        directories,
        extensions=(".md", ".markdown"),
        recursive=recursive,
        max_files=max_files,
    )


@dataclass(frozen=True)
class IngestPlanItem:
    path: Path
    ingestable: bool
    reason: str | None = None


def plan_file_ingest(
    config: WikiConfig,
    paths: Iterable[Path],
    *,
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS,
) -> list[IngestPlanItem]:
    exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
    items: list[IngestPlanItem] = []
    for path in paths:
        resolved = path.resolve()
        try:
            ensure_within(resolved, config.allowed_roots)
        except LLMWikiError as exc:
            items.append(IngestPlanItem(resolved, False, exc.message))
            continue
        if resolved.suffix.lower() not in exts:
            items.append(IngestPlanItem(resolved, False, "unsupported_extension"))
            continue
        items.append(IngestPlanItem(resolved, True, None))
    return items


def plan_markdown_ingest(config: WikiConfig, paths: Iterable[Path]) -> list[IngestPlanItem]:
    """Legacy helper: plan ingest for markdown files."""
    return plan_file_ingest(config, paths, extensions=(".md", ".markdown"))


def ingest_planned_paths(
    service: WikiService,
    paths: Iterable[Path],
    *,
    rights: str = "unknown",
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS,
) -> list[dict[str, Any]]:
    """Ingest each valid path; return per-file result dicts (ok or error)."""
    outcomes: list[dict[str, Any]] = []
    for item in plan_file_ingest(service.config, paths, extensions=extensions):
        if not item.ingestable:
            outcomes.append(
                {
                    "ok": False,
                    "path": str(item.path),
                    "error": {"code": "skipped", "message": item.reason or "skipped"},
                }
            )
            continue
        try:
            result = service.ingest_file(item.path, rights=rights)
            outcomes.append({"ok": True, "path": str(item.path), "result": result})
        except LLMWikiError as exc:
            outcomes.append(
                {
                    "ok": False,
                    "path": str(item.path),
                    "error": {"code": exc.code, "message": exc.message},
                }
            )
    return outcomes


def ingest_markdown_paths(
    service: WikiService,
    paths: Iterable[Path],
    *,
    rights: str = "unknown",
) -> list[dict[str, Any]]:
    """Legacy helper: ingest markdown paths."""
    return ingest_planned_paths(service, paths, rights=rights, extensions=(".md", ".markdown"))


def verify_and_cleanup_files(
    service: WikiService,
    paths: list[Path],
) -> list[dict[str, Any]]:
    """Verify stored SHA-256 byte digest in .llmwiki/objects/ before unlinking source files."""
    results: list[dict[str, Any]] = []
    with service.store.transaction() as con:
        for p in paths:
            resolved = p.resolve()
            if not resolved.exists() or not resolved.is_file():
                results.append({"path": str(resolved), "deleted": False, "reason": "not_found"})
                continue
            file_bytes = resolved.read_bytes()
            h = hashlib.sha256(file_bytes).hexdigest()

            row = con.execute(
                """SELECT sr.digest, sr.content_path FROM sources s
                   JOIN source_revisions sr ON s.current_revision_id = sr.id
                   WHERE sr.digest = ?""",
                (h,),
            ).fetchone()
            if not row:
                results.append({"path": str(resolved), "deleted": False, "reason": "not_in_store"})
                continue

            obj_path = service.config.db_path.parent / row["content_path"]
            if not obj_path.exists() or hashlib.sha256(obj_path.read_bytes()).hexdigest() != h:
                results.append({"path": str(resolved), "deleted": False, "reason": "object_mismatch"})
                continue

            resolved.unlink()
            results.append({"path": str(resolved), "deleted": True, "digest": h})
    return results


def auto_compile_revisions(
    service: WikiService,
    revision_ids: list[str],
) -> dict[str, Any]:
    """Extract representative candidate claims with exact locators and atomically apply them."""
    if not revision_ids:
        return {"count": 0, "claim_revision_ids": []}

    claims_payload: list[dict[str, Any]] = []
    with service.store.transaction() as con:
        for rev_id in revision_ids:
            row = con.execute(
                """SELECT s.display_name, sr.extracted_text, sr.extraction_json
                   FROM source_revisions sr JOIN sources s ON s.id = sr.source_id
                   WHERE sr.id = ?""",
                (rev_id,),
            ).fetchone()
            if not row:
                continue
            text = row["extracted_text"] or ""
            if not text.strip():
                continue

            # Derive entity name from display_name or first heading
            display = row["display_name"] or "Document"
            clean_name = display.replace(".md", "").replace(".txt", "").replace(".pdf", "")
            if clean_name.startswith("cursor_"):
                clean_name = clean_name[len("cursor_"):]
            entity_name = clean_name.replace("_", " ").replace("-", " ").strip().title()

            # Find a representative non-header paragraph or sentence
            cursor_idx = text.find("**Cursor**")
            sub = text[cursor_idx + len("**Cursor**"):].strip() if cursor_idx != -1 else text
            lines = [
                line.strip()
                for line in sub.splitlines()
                if len(line.strip()) > 30
                and not line.strip().startswith("---")
                and not line.strip().startswith("#")
                and not line.strip().startswith("```")
                and not line.strip().startswith(">")
            ]
            if not lines:
                lines = [
                    line.strip()
                    for line in text.splitlines()
                    if len(line.strip()) > 20 and not line.strip().startswith("#")
                ]

            if not lines:
                continue

            target_quote = lines[0]
            start = text.find(target_quote)
            if start == -1:
                continue
            end = start + len(target_quote)
            line_start = text.count("\n", 0, start) + 1
            line_end = text.count("\n", 0, max(start, end - 1)) + 1
            exact = text[start:end]

            claims_payload.append({
                "entity": {"name": entity_name},
                "text": f"Fact extracted from {display}: {target_quote}",
                "evidence": [{
                    "source_revision_id": rev_id,
                    "locator": {
                        "kind": "text",
                        "char_start": start,
                        "char_end": end,
                        "line_start": line_start,
                        "line_end": line_end,
                    },
                    "quote": exact,
                }],
            })

    if not claims_payload:
        return {"count": 0, "claim_revision_ids": []}

    export_res = service.compile_export(revision_ids)
    apply_payload = {
        "version": 1,
        "run_id": export_res["run_id"],
        "state_version": export_res["state_version"],
        "claims": claims_payload,
    }
    return service.compile_apply(apply_payload)


def consume_download_pipeline(
    wiki_root: Path,
    *,
    directories: list[Path] | None = None,
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS,
    discover: bool = True,
    recursive: bool = False,
    max_files: int = 200,
    rights: str = "unknown",
    run: bool = False,
    auto_compile: bool = False,
    render: bool = False,
    cleanup: bool = False,
) -> dict[str, Any]:
    """Execute the end-to-end download ingest, compile, render, and cleanup pipeline."""
    service = WikiService(wiki_root)
    config = service.config
    dirs: list[Path] = []
    if discover:
        dirs.extend(discover_download_directories(config.allowed_roots))
    if directories:
        dirs.extend(path.resolve() for path in directories)

    seen: set[Path] = set()
    unique_dirs: list[Path] = []
    for d in dirs:
        r = d.resolve()
        if r not in seen and r.is_dir():
            seen.add(r)
            unique_dirs.append(r)

    files = collect_download_files(unique_dirs, extensions=extensions, recursive=recursive, max_files=max_files)
    plan = plan_file_ingest(config, files, extensions=extensions)
    summary: dict[str, Any] = {
        "wiki_root": str(config.root.resolve()),
        "directories": [str(p) for p in unique_dirs],
        "file_count": len(plan),
        "ingestable_count": sum(1 for p in plan if p.ingestable),
        "run": run,
        "rights": rights,
        "recursive": recursive,
        "max_files": max_files,
        "extensions": list(extensions),
    }
    if not run:
        summary["plan"] = [
            {
                "path": str(item.path),
                "ingestable": item.ingestable,
                "reason": item.reason,
            }
            for item in plan
        ]
        return summary

    ingestable_paths = [item.path for item in plan if item.ingestable]
    outcomes = ingest_planned_paths(service, ingestable_paths, rights=rights, extensions=extensions)
    summary["results"] = outcomes
    summary["ingested"] = sum(1 for row in outcomes if row.get("ok"))
    summary["failed"] = sum(1 for row in outcomes if not row.get("ok"))

    # Extract successfully ingested revision IDs
    revision_ids: list[str] = []
    successful_paths: list[Path] = []
    for row in outcomes:
        if row.get("ok") and "result" in row:
            res = row["result"]
            rev_id = res.get("revision_id") or res.get("source_revision_id")
            if rev_id:
                revision_ids.append(rev_id)
            successful_paths.append(Path(row["path"]))

    # Optional auto-compilation
    if auto_compile and revision_ids:
        compile_res = auto_compile_revisions(service, revision_ids)
        summary["compiled_claims"] = compile_res.get("count", 0)
    else:
        summary["compiled_claims"] = 0

    # Optional render
    if render:
        service.validate()
        render_res = service.render(include_unreviewed=True)
        summary["rendered_pages"] = render_res.get("count", 0)
    else:
        summary["rendered_pages"] = 0

    # Optional cleanup of verified files
    if cleanup and successful_paths:
        cleanup_res = verify_and_cleanup_files(service, successful_paths)
        summary["cleaned_files"] = sum(1 for row in cleanup_res if row.get("deleted"))
        summary["cleanup_details"] = cleanup_res
    else:
        summary["cleaned_files"] = 0

    return summary


def consume_download_markdown(
    wiki_root: Path,
    *,
    directories: list[Path] | None = None,
    discover: bool = True,
    recursive: bool = False,
    max_files: int = 200,
    rights: str = "unknown",
    run: bool = False,
) -> dict[str, Any]:
    """Legacy helper: dry-run or ingest markdown from Downloads-style folders."""
    return consume_download_pipeline(
        wiki_root,
        directories=directories,
        extensions=(".md", ".markdown"),
        discover=discover,
        recursive=recursive,
        max_files=max_files,
        rights=rights,
        run=run,
    )
