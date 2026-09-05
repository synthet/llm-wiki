"""The :class:`Wiki` collection: discovery, loading and link resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .model import Page

# Directory names that hold rendered Markdown pages, relative to the wiki root.
PAGE_DIRS = ("pages", "knowledge/pages")
CONFIG_NAMES = ("wiki.yaml", "wiki.yml", ".llmwiki.yaml", ".llmwiki.yml")


class Wiki:
    """A loaded collection of pages rooted at ``root``.

    ``root`` is the wiki directory (the one that contains a ``pages/`` folder
    and/or a ``wiki.yaml``). Pages are discovered recursively under the known
    page directories, or directly under ``root`` if none exist.
    """

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.pages: List[Page] = []
        self._by_name: Dict[str, Page] = {}
        self._by_id: Dict[str, Page] = {}

    # -- discovery -------------------------------------------------------------
    @classmethod
    def discover(cls, start: Optional[Path] = None) -> "Wiki":
        """Find the nearest wiki root at or above ``start`` and load it."""
        start = Path(start or Path.cwd()).resolve()
        candidates = [start] + list(start.parents)
        for d in candidates:
            for cfg in CONFIG_NAMES:
                if (d / cfg).exists():
                    return cls(d).load()
            for pd in PAGE_DIRS:
                if (d / pd).is_dir():
                    return cls(d).load()
            if (d / "wiki").is_dir() and any(
                (d / "wiki" / pd).is_dir() or (d / "wiki").glob("*.md")
                for pd in ("pages",)
            ):
                return cls(d / "wiki").load()
        # Fall back to treating start as the root.
        return cls(start).load()

    def page_root(self) -> Path:
        for pd in PAGE_DIRS:
            if (self.root / pd).is_dir():
                return self.root / pd
        return self.root

    # -- loading ---------------------------------------------------------------
    def load(self) -> "Wiki":
        self.pages = []
        proot = self.page_root()
        for path in sorted(proot.rglob("*.md")):
            if any(part.startswith(".") for part in path.relative_to(self.root).parts):
                continue
            try:
                self.pages.append(Page.load(path))
            except Exception as exc:  # pragma: no cover - unreadable file
                # Represent unreadable files as empty pages carrying the error.
                p = Page(path=path, frontmatter={}, body="", raw="", parse_error=str(exc))
                self.pages.append(p)
        self._reindex()
        return self

    def _reindex(self) -> None:
        self._by_name.clear()
        self._by_id.clear()
        for page in self.pages:
            self._by_id.setdefault(page.id, page)
            for name in page.names:
                key = _norm(name)
                # First writer wins for a given key; keeps resolution stable.
                self._by_name.setdefault(key, page)

    # -- lookup ----------------------------------------------------------------
    def get(self, ref: str) -> Optional[Page]:
        if ref in self._by_id:
            return self._by_id[ref]
        return self._by_name.get(_norm(ref))

    def resolve_link(self, target: str) -> Optional[Page]:
        return self.get(target)

    def rel(self, page: Page) -> str:
        try:
            return str(page.path.relative_to(self.root))
        except ValueError:
            return str(page.path)

    # -- graph -----------------------------------------------------------------
    def outbound(self, page: Page) -> List[Page]:
        seen, out = set(), []
        for link in page.links:
            tgt = self.resolve_link(link.target)
            if tgt and tgt.id not in seen and tgt.id != page.id:
                seen.add(tgt.id)
                out.append(tgt)
        return out

    def backlinks(self, page: Page) -> List[Page]:
        out = []
        for other in self.pages:
            if other.id == page.id:
                continue
            for link in other.links:
                if self.resolve_link(link.target) is page:
                    out.append(other)
                    break
        return out

    def __len__(self) -> int:
        return len(self.pages)


def _norm(name: str) -> str:
    return str(name).strip().lower()
