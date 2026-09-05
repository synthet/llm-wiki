"""Search over an indexed wiki, with optional one-hop wikilink expansion."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .index import Index, SearchResult
from .wiki import Wiki


def search(
    root: Path,
    query: str,
    limit: int = 10,
    status: Optional[str] = None,
    type_: Optional[str] = None,
    expand: bool = False,
    wiki: Optional[Wiki] = None,
) -> List[SearchResult]:
    """Search the index at ``root``.

    When ``expand`` is true, results are augmented with pages directly linked
    from the top hits (marked ``matched_via='wikilink'``), reflecting the
    hybrid compile+retrieval design where wikilinks carry curated structure.
    """
    idx = Index(root)
    results = idx.search(query, limit=limit, status=status, type_=type_)
    if not expand or not results:
        return results

    seen = {r.id for r in results}
    extra: List[SearchResult] = []
    for r in results[: min(5, len(results))]:
        for linked_id in idx.links_of(r.id):
            if linked_id in seen:
                continue
            meta = idx.meta(linked_id)
            if not meta:
                continue
            if status and meta["status"] != status:
                continue
            if type_ and meta["type"] != type_:
                continue
            seen.add(linked_id)
            extra.append(SearchResult(
                id=meta["id"], title=meta["title"], path=meta["path"],
                status=meta["status"], type=meta["type"],
                score=r.score * 0.4, snippet=f"(linked from {r.title})",
                tags=meta["tags"], matched_via="wikilink",
            ))
    combined = results + extra
    combined.sort(key=lambda x: -x.score)
    return combined[: limit + len(extra)]
