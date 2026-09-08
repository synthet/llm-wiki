"""Stable public errors shared by CLI and MCP transports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMWikiError(Exception):
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    retryable: bool = False
    next_steps: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return self.message

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "retryable": self.retryable,
            "next_steps": self.next_steps,
        }


def error(code: str, message: str, **details: Any) -> LLMWikiError:
    return LLMWikiError(code=code, message=message, details=details)
