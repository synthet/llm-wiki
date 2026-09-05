"""Structural and semantic validation for an LLM Wiki.

Rules encode the LLM Wiki invariants: valid frontmatter, machine-readable
review states, resolvable wikilinks, stable/unique identity, claim→evidence
coverage, source integrity, freshness and rights hygiene.

Each finding is a :class:`~llmwiki.model.PageIssue` with a severity of
``error`` (fails CI), ``warning`` or ``info``.
"""

from __future__ import annotations

import datetime as _dt
from typing import Callable, Dict, List

from .model import (
    CLAIM_STATUSES,
    PAGE_TYPES,
    STATUSES,
    Page,
    PageIssue,
    parse_ts,
)
from .wiki import Wiki

REQUIRED_FIELDS = ("id", "title", "type", "status")

# Rules that promote to plain warnings when this many days stale, etc.
_now = lambda: _dt.datetime.now(_dt.timezone.utc)  # noqa: E731


def lint(wiki: Wiki, strict: bool = False) -> List[PageIssue]:
    """Run all rules over ``wiki``.

    ``strict`` promotes selected warnings (missing evidence on reviewed claims,
    stale freshness) to errors.
    """
    issues: List[PageIssue] = []
    seen_ids: Dict[str, str] = {}
    seen_slugs: Dict[str, str] = {}

    for page in wiki.pages:
        rel = wiki.rel(page)
        issues.extend(_lint_page(wiki, page, rel, strict, seen_ids, seen_slugs))

    return issues


def _lint_page(
    wiki: Wiki,
    page: Page,
    rel: str,
    strict: bool,
    seen_ids: Dict[str, str],
    seen_slugs: Dict[str, str],
) -> List[PageIssue]:
    out: List[PageIssue] = []

    def add(rule, severity, message, line=0):
        out.append(PageIssue(path=rel, rule=rule, severity=severity, message=message, line=line))

    # --- frontmatter parseability -------------------------------------------
    if page.parse_error:
        add("frontmatter-parse", "error", f"cannot parse frontmatter: {page.parse_error}")
        return out  # nothing else is reliable

    if not page.frontmatter:
        add("frontmatter-missing", "error", "page has no YAML frontmatter block")
        return out

    # --- required fields -----------------------------------------------------
    for fieldname in REQUIRED_FIELDS:
        if not page.frontmatter.get(fieldname):
            sev = "error" if fieldname in ("id", "title") else "warning"
            add("required-field", sev, f"missing required frontmatter field '{fieldname}'")

    # --- controlled vocabularies --------------------------------------------
    if page.frontmatter.get("type") and page.type not in PAGE_TYPES:
        add("invalid-type", "warning", f"unknown type '{page.type}' (expected {list(PAGE_TYPES)})")
    if page.frontmatter.get("status") and page.status not in STATUSES:
        add("invalid-status", "error", f"unknown status '{page.status}' (expected {list(STATUSES)})")

    # --- identity uniqueness -------------------------------------------------
    if page.frontmatter.get("id"):
        prev = seen_ids.get(page.id)
        if prev:
            add("duplicate-id", "error", f"id '{page.id}' also used by {prev}")
        else:
            seen_ids[page.id] = rel
    prev_slug = seen_slugs.get(page.slug.lower())
    if prev_slug:
        add("duplicate-slug", "error", f"slug '{page.slug}' also used by {prev_slug}")
    else:
        seen_slugs[page.slug.lower()] = rel

    # --- wikilinks resolve ---------------------------------------------------
    for link in page.links:
        if wiki.resolve_link(link.target) is None:
            add("broken-wikilink", "error", f"unresolved wikilink [[{link.target}]]", link.line)

    # --- sources integrity ---------------------------------------------------
    source_ids = set()
    for i, src in enumerate(page.sources):
        if not src.get("id"):
            add("source-id", "warning", f"sources[{i}] has no 'id'")
        else:
            source_ids.add(str(src["id"]))
        if not src.get("uri"):
            add("source-uri", "info", f"source '{src.get('id', i)}' has no 'uri'")
        digest = src.get("digest")
        if digest and not str(digest).startswith("sha256:"):
            add("source-digest", "warning", f"source '{src.get('id', i)}' digest is not a sha256: value")

    # --- claims: evidence coverage & integrity ------------------------------
    for i, claim in enumerate(page.claims):
        cid = claim.get("id") or f"claims[{i}]"
        cstatus = str(claim.get("status") or page.status)
        if claim.get("status") and cstatus not in CLAIM_STATUSES:
            add("invalid-claim-status", "warning", f"claim {cid} has unknown status '{cstatus}'")
        if not claim.get("text"):
            add("claim-text", "warning", f"claim {cid} has no 'text'")
        evidence = claim.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = []
        # Reviewed claims must be grounded in evidence.
        if not evidence and cstatus in ("reviewed", "disputed"):
            sev = "error" if strict else "warning"
            add("missing-evidence", sev, f"{cstatus} claim {cid} has no evidence")
        for ev in evidence:
            if not isinstance(ev, dict):
                continue
            sref = ev.get("source_id")
            if sref and source_ids and str(sref) not in source_ids:
                add(
                    "dangling-evidence",
                    "warning",
                    f"claim {cid} cites source '{sref}' not listed in page sources",
                )

    # Reviewed page with zero claims and zero sources -> likely ungrounded.
    if page.status == "reviewed" and not page.claims and not page.sources and page.type in ("entity", "topic"):
        add("ungrounded-page", "warning", "reviewed page has neither claims nor sources")

    # --- freshness -----------------------------------------------------------
    fresh = page.freshness
    if fresh:
        expires = parse_ts(fresh.get("expires_at"))
        if expires is not None:
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=_dt.timezone.utc)
            if expires < _now():
                sev = "error" if strict else "warning"
                add("stale", sev, f"freshness.expires_at {fresh.get('expires_at')} is in the past")
        if str(fresh.get("stale")).lower() == "true" and page.status == "reviewed":
            add("stale-reviewed", "warning", "page marked freshness.stale but status is 'reviewed'")

    # --- rights --------------------------------------------------------------
    rights = page.rights
    if rights:
        if rights.get("redistribution_allowed") is True and not rights.get("license_expression") and not rights.get("license"):
            add("rights-license", "warning", "redistribution_allowed is true but no license is declared")

    return out


def summarize(issues: List[PageIssue]) -> Dict[str, int]:
    counts = {"error": 0, "warning": 0, "info": 0}
    for issue in issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1
    return counts


# Public registry of rule ids for documentation/help.
RULES: Dict[str, str] = {
    "frontmatter-parse": "frontmatter must be valid YAML",
    "frontmatter-missing": "page must have a frontmatter block",
    "required-field": "id, title, type, status must be present",
    "invalid-type": "type must be one of the known page types",
    "invalid-status": "status must be a known review state",
    "duplicate-id": "page ids must be unique",
    "duplicate-slug": "page slugs must be unique",
    "broken-wikilink": "[[wikilinks]] must resolve to a page",
    "source-id": "each source should carry an id",
    "source-uri": "each source should carry a uri",
    "source-digest": "source digests should be sha256: values",
    "invalid-claim-status": "claim status must be a known state",
    "claim-text": "each claim should carry text",
    "missing-evidence": "reviewed/disputed claims must cite evidence",
    "dangling-evidence": "claim evidence must reference a listed source",
    "ungrounded-page": "reviewed entity/topic pages should carry claims or sources",
    "stale": "freshness.expires_at must be in the future",
    "stale-reviewed": "a reviewed page should not be flagged stale",
    "rights-license": "redistributable pages must declare a license",
}
