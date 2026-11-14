"""Context retrieval and bounded memory-to-cognition integration."""
from __future__ import annotations
import math
import time
from typing import Protocol
from tara_app.memory import MemoryKind, MemorySearchResult
from .attention import AttentionMechanism
from .models import AttentionFeatures, CognitiveContext, CognitiveRequest, ContextItem

class MemoryRecallPort(Protocol):
    def recall(self, query: str, *, kinds: tuple[MemoryKind, ...], limit: int, min_score: float) -> tuple[MemorySearchResult, ...]: ...

class ContextBuilder:
    """Build request context from memory and optional transient observations."""
    def __init__(self, memory: MemoryRecallPort, *, attention: AttentionMechanism | None = None, recency_half_life_seconds: float = 86_400.0) -> None:
        if isinstance(recency_half_life_seconds, bool) or not isinstance(recency_half_life_seconds, (int, float)) or not math.isfinite(recency_half_life_seconds) or recency_half_life_seconds <= 0:
            raise ValueError("recency_half_life_seconds must be finite and positive")
        self.memory = memory
        self.attention = attention or AttentionMechanism()
        self.recency_half_life_seconds = float(recency_half_life_seconds)
    def build(self, request: CognitiveRequest, *, observations: tuple[ContextItem, ...] = (), now: float | None = None) -> CognitiveContext:
        timestamp = time.time() if now is None else now
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
            raise ValueError("now must be a finite timestamp")
        results = self.memory.recall(request.query, kinds=(MemoryKind.WORKING, MemoryKind.EPISODIC, MemoryKind.SEMANTIC), limit=min(100, request.max_context_items * 4), min_score=0.0)
        candidates: list[ContextItem] = list(observations)
        for result in results:
            age = max(0.0, timestamp - result.record.created_at)
            recency = math.exp(-math.log(2.0) * age / self.recency_half_life_seconds)
            candidates.append(ContextItem(
                item_id=result.record.memory_id,
                content=result.record.content,
                source=result.record.kind.value,
                features=AttentionFeatures(
                    relevance=result.score, importance=result.record.importance,
                    recency=recency, salience=result.record.importance, confidence=1.0,
                ),
            ))
        return CognitiveContext(request, self.attention.select(candidates, limit=request.max_context_items), float(timestamp))
