"""Core data model for LLM Wiki pages.

A page is a Markdown file with YAML frontmatter. Frontmatter carries the
claim-centric, provenance-aware metadata recommended by the LLM Wiki research
baseline: stable identity, review ``status``, ``sources``, ``claims`` with
per-claim evidence, ``freshness`` and ``rights``.

Design invariants (mirrored by the linter):
  * the wiki is a *projection* of claims; every reviewed factual claim carries
    evidence tied to a specific source,
  * ``status`` is machine-readable data, not prose,
  * filenames/slugs are aliases, never canonical identity.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import yamlio

PAGE_TYPES = ("entity", "topic", "note", "index")
STATUSES = ("candidate", "reviewed", "disputed", "stale", "superseded", "retracted")
CLAIM_STATUSES = ("candidate", "reviewed", "disputed", "superseded", "retracted")

# [[Target]] or [[Target|Display]] or [[Target#anchor]]
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    s = _SLUG_RE.sub("-", text.strip().lower()).strip("-")
    return s or "untitled"


def content_digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class WikiLink:
    target: str  # raw link target (title/slug/id/alias)
    display: Optional[str] = None
    line: int = 0


@dataclass
class Page:
    """A parsed wiki page."""

    path: Path
    frontmatter: Dict[str, Any]
    body: str
    raw: str
    parse_error: Optional[str] = None
    links: List[WikiLink] = field(default_factory=list)

    # -- convenience accessors -------------------------------------------------
    @property
    def title(self) -> str:
        return str(self.frontmatter.get("title") or self.path.stem)

    @property
    def id(self) -> str:
        pid = self.frontmatter.get("id")
        if pid:
            return str(pid)
        return f"page:{self.slug}"

    @property
    def slug(self) -> str:
        s = self.frontmatter.get("slug")
        if s:
            return str(s)
        return self.path.stem

    @property
    def type(self) -> str:
        return str(self.frontmatter.get("type") or "note")

    @property
    def status(self) -> str:
        return str(self.frontmatter.get("status") or "candidate")

    @property
    def tags(self) -> List[str]:
        t = self.frontmatter.get("tags") or []
        return [str(x) for x in t] if isinstance(t, list) else [str(t)]

    @property
    def aliases(self) -> List[str]:
        a = self.frontmatter.get("aliases") or []
        return [str(x) for x in a] if isinstance(a, list) else [str(a)]

    @property
    def sources(self) -> List[Dict[str, Any]]:
        s = self.frontmatter.get("sources") or []
        return [x for x in s if isinstance(x, dict)] if isinstance(s, list) else []

    @property
    def claims(self) -> List[Dict[str, Any]]:
        c = self.frontmatter.get("claims") or []
        return [x for x in c if isinstance(x, dict)] if isinstance(c, list) else []

    @property
    def freshness(self) -> Dict[str, Any]:
        f = self.frontmatter.get("freshness") or {}
        return f if isinstance(f, dict) else {}

    @property
    def rights(self) -> Dict[str, Any]:
        r = self.frontmatter.get("rights") or {}
        return r if isinstance(r, dict) else {}

    @property
    def names(self) -> List[str]:
        """All identifiers this page can be referenced by."""
        out = [self.id, self.slug, self.title, self.path.stem]
        out.extend(self.aliases)
        return out

    def text_for_index(self) -> str:
        parts = [self.title, " ".join(self.aliases), " ".join(self.tags)]
        for claim in self.claims:
            if claim.get("text"):
                parts.append(str(claim["text"]))
        parts.append(strip_markdown(self.body))
        return "\n".join(p for p in parts if p)

    # -- construction ----------------------------------------------------------
    @classmethod
    def load(cls, path: Path) -> "Page":
        raw = Path(path).read_text(encoding="utf-8")
        error = None
        try:
            fm, body, _ = yamlio.split_frontmatter(raw)
        except Exception as exc:  # malformed frontmatter -> keep going for lint
            fm, body, error = {}, raw, str(exc)
        page = cls(path=Path(path), frontmatter=fm, body=body, raw=raw, parse_error=error)
        page.links = extract_links(body)
        return page


_INLINE_CODE_RE = re.compile(r"`[^`]*`")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def extract_links(body: str) -> List[WikiLink]:
    """Find ``[[wikilinks]]`` in prose, ignoring fenced and inline code.

    Links that appear inside code fences or inline `code spans` are examples,
    not real links, so they must not be flagged as broken.
    """
    links: List[WikiLink] = []
    in_fence = False
    for i, line in enumerate(body.splitlines(), start=1):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        scan = _INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), line)
        for m in WIKILINK_RE.finditer(scan):
            links.append(WikiLink(target=m.group(1).strip(), display=m.group(2), line=i))
    return links


_MD_STRIP_RES = [
    (re.compile(r"```.*?```", re.DOTALL), " "),
    (re.compile(r"`[^`]*`"), " "),
    (re.compile(r"!\[[^\]]*\]\([^)]*\)"), " "),
    (re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]"), lambda m: m.group(2) or m.group(1)),
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),
    (re.compile(r"^[#>\-\*\+\s]+", re.MULTILINE), " "),
    (re.compile(r"[*_~]"), ""),
]


def strip_markdown(body: str) -> str:
    text = body
    for rx, repl in _MD_STRIP_RES:
        text = rx.sub(repl, text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class PageIssue:
    """A single linter finding."""

    path: str
    rule: str
    severity: str  # "error" | "warning" | "info"
    message: str
    line: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "line": self.line,
        }

    def format(self) -> str:
        loc = f"{self.path}:{self.line}" if self.line else self.path
        return f"{loc}: {self.severity}: [{self.rule}] {self.message}"


def parse_ts(value: Any) -> Optional[_dt.datetime]:
    """Best-effort parse of an ISO-8601 date/datetime from frontmatter."""
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        return value
    if isinstance(value, _dt.date):
        return _dt.datetime(value.year, value.month, value.day)
    s = str(value).strip()
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return _dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return _dt.datetime.fromisoformat(s)
    except ValueError:
        return None
