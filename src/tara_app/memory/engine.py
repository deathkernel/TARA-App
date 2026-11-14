"""Memory lifecycle orchestration for the SN-86 cognitive runtime."""

from __future__ import annotations

import time
import uuid
from collections.abc import Sequence

from .models import MemoryKind, MemoryRecord, MemorySearchResult
from .repository import MemoryRepository
from .working import WorkingMemory


class MemoryEngine:
    """Coordinate ephemeral working memory and approved long-term memory."""

    def __init__(
        self,
        repository: MemoryRepository,
        *,
        working_capacity: int = 32,
    ) -> None:
        self.repository = repository
        self.working = WorkingMemory(working_capacity)

    def capture(
        self,
        content: str,
        *,
        importance: float = 0.5,
        tags: Sequence[str] = (),
        source: str = "user",
    ) -> MemoryRecord:
        """Capture an observation in session memory without disk persistence."""
        record = MemoryRecord(
            memory_id=uuid.uuid4().hex,
            kind=MemoryKind.WORKING,
            content=content,
            created_at=time.time(),
            importance=importance,
            tags=tuple(tags),
            source=source,
        )
        self.working.add(record)
        return record

    def consolidate(
        self,
        memory_id: str,
        *,
        target_kind: MemoryKind,
    ) -> MemoryRecord:
        """Promote one working item to approved episodic or semantic memory."""
        if target_kind not in {MemoryKind.EPISODIC, MemoryKind.SEMANTIC}:
            raise ValueError("target_kind must be EPISODIC or SEMANTIC")
        working_record = self.working.get(memory_id)
        if working_record is None:
            raise KeyError(memory_id)
        record = MemoryRecord(
            memory_id=working_record.memory_id,
            kind=target_kind,
            content=working_record.content,
            created_at=working_record.created_at,
            importance=working_record.importance,
            tags=working_record.tags,
            source=working_record.source,
        )
        self.repository.upsert(record)
        self.working.remove(memory_id)
        return record

    def remember(
        self,
        content: str,
        *,
        kind: MemoryKind,
        importance: float = 0.5,
        tags: Sequence[str] = (),
        source: str = "user",
        memory_id: str | None = None,
    ) -> MemoryRecord:
        """Store an explicitly typed long-term memory after authorization."""
        if kind not in {MemoryKind.EPISODIC, MemoryKind.SEMANTIC}:
            raise ValueError("long-term kind must be EPISODIC or SEMANTIC")
        record = MemoryRecord(
            memory_id=memory_id or uuid.uuid4().hex,
            kind=kind,
            content=content,
            created_at=time.time(),
            importance=importance,
            tags=tuple(tags),
            source=source,
        )
        self.repository.upsert(record)
        return record

    def recall(
        self,
        query: str,
        *,
        kinds: Sequence[MemoryKind] = (
            MemoryKind.WORKING,
            MemoryKind.EPISODIC,
            MemoryKind.SEMANTIC,
        ),
        limit: int = 10,
        min_score: float = 0.0,
    ) -> tuple[MemorySearchResult, ...]:
        """Retrieve across selected stores using transparent lexical scoring."""
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if not 0.0 <= min_score <= 1.0:
            raise ValueError("min_score must be in [0, 1]")
        results: list[MemorySearchResult] = []
        if MemoryKind.WORKING in kinds:
            query_tokens = set(query.lower().split())
            for record in self.working.recent():
                content_tokens = set(record.content.lower().split())
                score = len(query_tokens & content_tokens) / len(query_tokens) if query_tokens else 0.0
                if score >= min_score and score > 0.0:
                    results.append(MemorySearchResult(record=record, score=min(1.0, score)))
        for kind in (MemoryKind.EPISODIC, MemoryKind.SEMANTIC):
            if kind in kinds:
                results.extend(
                    self.repository.search(
                        query,
                        kind=kind,
                        limit=limit,
                        min_score=min_score,
                    )
                )
        results.sort(
            key=lambda item: (
                -item.score,
                -item.record.importance,
                -item.record.created_at,
                item.record.memory_id,
            )
        )
        return tuple(results[:limit])

    def forget(self, memory_id: str) -> bool:
        """Remove a session item or request an approved persistent deletion."""
        working_record = self.working.remove(memory_id)
        if working_record is not None:
            return True
        return self.repository.delete(memory_id)
