"""Project configuration and safe root discovery."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .errors import error
from .semantic_retrieval import RetrievalConfig


@dataclass(frozen=True)
class WikiConfig:
    root: Path
    data_dir: Path
    pages_dir: Path
    notes_dir: Path
    allowed_roots: tuple[Path, ...]
    max_bytes: int = 25 * 1024 * 1024
    max_download_bytes: int = 25 * 1024 * 1024
    max_pdf_pages: int = 500
    parse_timeout_seconds: float = 30.0
    http_timeout_seconds: float = 20.0
    retrieval: RetrievalConfig = RetrievalConfig()

    @property
    def db_path(self) -> Path:
        return self.data_dir / "wiki.db"

    @property
    def objects_dir(self) -> Path:
        return self.data_dir / "objects"

    @classmethod
    def load(cls, root: Path) -> WikiConfig:
        root = root.resolve()
        load_dotenv(root / ".env")
        config_path = root / ".llmwiki" / "config.yaml"
        values: dict[str, Any] = {}
        if config_path.exists():
            loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            if loaded is not None and not isinstance(loaded, dict):
                raise error("invalid_config", "Wiki config must contain a YAML mapping.")
            values = loaded or {}
        limits = values.get("limits", {})
        if not isinstance(limits, dict):
            raise error("invalid_config", "Config 'limits' must be a mapping.")
        allowed = values.get("allowed_roots", ["."])
        if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
            raise error("invalid_config", "Config 'allowed_roots' must be a list of paths.")
        allowed_roots = tuple(_resolve_under(root, item) for item in allowed)
        retrieval_values = values.get("retrieval", {})
        if retrieval_values is not None and not isinstance(retrieval_values, dict):
            raise error("invalid_config", "Config 'retrieval' must be a mapping.")
        retrieval_values = retrieval_values or {}
        retrieval = RetrievalConfig(
            semantic=str(retrieval_values.get("semantic", "off")),
            candidate_pool_multiplier=int(retrieval_values.get("candidate_pool_multiplier", 5)),
            max_candidate_pool=int(retrieval_values.get("max_candidate_pool", 50)),
            citation_support_threshold=float(retrieval_values.get("citation_support_threshold", 0.55)),
            lexical_blend=float(retrieval_values.get("lexical_blend", 0.25)),
            api_key_env=str(retrieval_values.get("api_key_env", "JEV_TOKEN")),
            timeout_seconds=float(retrieval_values.get("timeout_seconds", 30.0)),
        )
        retrieval.validate()
        return cls(
            root=root,
            data_dir=root / ".llmwiki",
            pages_dir=root / "wiki" / "pages",
            notes_dir=root / "wiki" / "notes",
            allowed_roots=allowed_roots,
            max_bytes=int(limits.get("max_bytes", 25 * 1024 * 1024)),
            max_download_bytes=int(limits.get("max_download_bytes", 25 * 1024 * 1024)),
            max_pdf_pages=int(limits.get("max_pdf_pages", 500)),
            parse_timeout_seconds=float(limits.get("parse_timeout_seconds", 30)),
            http_timeout_seconds=float(limits.get("http_timeout_seconds", 20)),
            retrieval=retrieval,
        )


def discover_root(start: Path | None = None, explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".llmwiki" / "config.yaml").is_file():
            return candidate
        if (candidate / "wiki" / "pages").is_dir() and (candidate / "pyproject.toml").exists():
            return candidate
    return current


def ensure_within(path: Path, allowed_roots: tuple[Path, ...]) -> Path:
    resolved = path.resolve(strict=True)
    if not any(resolved == root or root in resolved.parents for root in allowed_roots):
        raise error(
            "path_outside_allowed_roots",
            "Source path is outside configured allowed roots.",
            path=str(resolved),
        )
    if path.is_symlink() and not any(resolved == root or root in resolved.parents for root in allowed_roots):
        raise error("symlink_escape", "Source symlink escapes configured allowed roots.")
    return resolved


def _resolve_under(root: Path, value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def load_dotenv(path: Path) -> int:
    """Load KEY=VALUE pairs from a local .env without overriding existing process env.

    Returns the number of newly set keys. Values are never logged or returned.
    """
    if not path.is_file():
        return 0
    loaded = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value
        loaded += 1
    return loaded
