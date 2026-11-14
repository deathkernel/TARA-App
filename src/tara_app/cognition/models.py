"""Typed contracts for SN-86 cognitive processing."""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from enum import StrEnum

def _unit_interval(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be in [0, 1]")

@dataclass(frozen=True, slots=True)
class CognitiveRequest:
    request_id: str
    query: str
    objective: str = ""
    max_context_items: int = 8
    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id must be non-empty")
        if not self.query.strip() or len(self.query) > 500:
            raise ValueError("query must contain 1 to 500 characters")
        if len(self.objective) > 500:
            raise ValueError("objective must not exceed 500 characters")
        if isinstance(self.max_context_items, bool) or not isinstance(self.max_context_items, int) or not 1 <= self.max_context_items <= 32:
            raise ValueError("max_context_items must be between 1 and 32")

@dataclass(frozen=True, slots=True)
class AttentionFeatures:
    relevance: float
    importance: float
    recency: float
    salience: float = 0.5
    confidence: float = 1.0
    def __post_init__(self) -> None:
        for name in ("relevance", "importance", "recency", "salience", "confidence"):
            _unit_interval(name, getattr(self, name))

@dataclass(frozen=True, slots=True)
class ContextItem:
    item_id: str
    content: str
    features: AttentionFeatures
    source: str = "memory"
    def __post_init__(self) -> None:
        if not self.item_id.strip() or not self.content.strip():
            raise ValueError("context item id and content must be non-empty")

@dataclass(frozen=True, slots=True)
class AttendedItem:
    item: ContextItem
    score: float
    feature_contributions: tuple[tuple[str, float], ...]

@dataclass(frozen=True, slots=True)
class CognitiveContext:
    request: CognitiveRequest
    items: tuple[AttendedItem, ...]
    created_at: float

@dataclass(frozen=True, slots=True)
class ActionOption:
    action_id: str
    description: str
    expected_utility: float
    confidence: float = 1.0
    risk: float = 0.0
    evidence_strength: float = 0.5
    def __post_init__(self) -> None:
        if not self.action_id.strip() or not self.description.strip():
            raise ValueError("action id and description must be non-empty")
        for name in ("expected_utility", "confidence", "risk", "evidence_strength"):
            _unit_interval(name, getattr(self, name))

class DecisionStatus(StrEnum):
    SELECTED = "selected"
    ABSTAINED = "abstained"

@dataclass(frozen=True, slots=True)
class DecisionResult:
    status: DecisionStatus
    selected_action: ActionOption | None
    score: float
    margin: float
    rationale: str
    ranked_options: tuple[tuple[str, float], ...] = ()

class GoalStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    BLOCKED = "blocked"

@dataclass(frozen=True, slots=True)
class Goal:
    goal_id: str
    description: str
    importance: float = 0.5
    urgency: float = 0.5
    relevance: float = 0.5
    deadline_at: float | None = None
    dependencies: tuple[str, ...] = ()
    status: GoalStatus = GoalStatus.PENDING
    def __post_init__(self) -> None:
        if not self.goal_id.strip() or not self.description.strip():
            raise ValueError("goal id and description must be non-empty")
        for name in ("importance", "urgency", "relevance"):
            _unit_interval(name, getattr(self, name))
        if self.deadline_at is not None and (isinstance(self.deadline_at, bool) or not isinstance(self.deadline_at, (int, float)) or not math.isfinite(self.deadline_at)):
            raise ValueError("deadline_at must be finite when supplied")
        if self.goal_id in self.dependencies:
            raise ValueError("a goal cannot depend on itself")
        if not isinstance(self.status, GoalStatus):
            raise TypeError("status must be a GoalStatus")

@dataclass(frozen=True, slots=True)
class ReasoningTrace:
    request_id: str
    stages: tuple[str, ...]
    context_item_ids: tuple[str, ...]
    decision: DecisionResult | None
    notes: tuple[str, ...] = field(default_factory=tuple)
