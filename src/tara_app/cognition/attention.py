"""Deterministic, explainable attention allocation."""
from __future__ import annotations
import math
from dataclasses import dataclass
from .models import AttendedItem, ContextItem

@dataclass(frozen=True, slots=True)
class AttentionWeights:
    relevance: float = 0.35
    importance: float = 0.20
    recency: float = 0.15
    salience: float = 0.15
    confidence: float = 0.15
    def __post_init__(self) -> None:
        values = (self.relevance, self.importance, self.recency, self.salience, self.confidence)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0.0 for value in values):
            raise ValueError("attention weights must be finite non-negative numbers")
        if abs(sum(values) - 1.0) > 1e-9:
            raise ValueError("attention weights must sum to 1")

class AttentionMechanism:
    """Rank candidate information using transparent weighted feature scoring."""
    def __init__(self, weights: AttentionWeights | None = None) -> None:
        self.weights = weights or AttentionWeights()
    def score(self, item: ContextItem) -> AttendedItem:
        features = item.features
        contributions = (
            ("relevance", self.weights.relevance * features.relevance),
            ("importance", self.weights.importance * features.importance),
            ("recency", self.weights.recency * features.recency),
            ("salience", self.weights.salience * features.salience),
            ("confidence", self.weights.confidence * features.confidence),
        )
        return AttendedItem(item, sum(value for _, value in contributions), contributions)
    def select(self, items: tuple[ContextItem, ...] | list[ContextItem], *, limit: int) -> tuple[AttendedItem, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        ranked = [self.score(item) for item in items]
        ranked.sort(key=lambda result: (-result.score, result.item.item_id))
        return tuple(ranked[:limit])
