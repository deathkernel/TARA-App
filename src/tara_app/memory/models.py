"""Typed records and contracts shared by TN-86 memory subsystems."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class MemoryKind(StrEnum):
    """Memory lifecycle/type; working memory is intentionally ephemeral."""

    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """A bounded, typed memory item independent of its storage backend."""

    memory_id: str
    kind: MemoryKind
    content: str
    created_at: float
    importance: float = 0.5
    tags: tuple[str, ...] = ()
    source: str = "user"

    def __post_init__(self) -> None:
        if not isinstance(self.memory_id, str) or not self.memory_id.strip():
            raise ValueError("memory_id must be non-empty text")
        if not isinstance(self.kind, MemoryKind):
            raise TypeError("kind must be a MemoryKind")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("content must be non-empty text")
        if len(self.content) > 8000:
            raise ValueError("content must not exceed 8000 characters")
        if not isinstance(self.created_at, (int, float)) or not math.isfinite(self.created_at):
            raise ValueError("created_at must be finite")
        if not isinstance(self.importance, (int, float)) or not math.isfinite(self.importance):
            raise ValueError("importance must be finite")
        if not 0.0 <= self.importance <= 1.0:
            raise ValueError("importance must be in [0, 1]")
        if len(self.tags) > 32 or any(not isinstance(tag, str) or not tag.strip() for tag in self.tags):
            raise ValueError("tags must contain at most 32 non-empty strings")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be non-empty text")


@dataclass(frozen=True, slots=True)
class MemorySearchResult:
    """A memory plus its transparent lexical relevance score."""

    record: MemoryRecord
    score: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.score) or not 0.0 <= self.score <= 1.0:
            raise ValueError("score must be in [0, 1]")
