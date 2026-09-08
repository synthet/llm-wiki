"""Local-first, evidence-bound knowledge compiler."""

from .errors import LLMWikiError
from .service import WikiService

__all__ = ["LLMWikiError", "WikiService"]
__version__ = "0.1.0"
