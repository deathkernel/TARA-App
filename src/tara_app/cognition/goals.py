"""Bounded goal storage and deterministic priority scheduling."""
from __future__ import annotations
import math
import time
from dataclasses import replace
from .models import Goal, GoalStatus

class GoalScheduler:
    """Prioritize goals without executing them or bypassing TARA permissions."""
    def __init__(self, *, capacity: int = 128) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or not 1 <= capacity <= 4096:
            raise ValueError("capacity must be between 1 and 4096")
        self.capacity = capacity
        self._goals: dict[str, Goal] = {}
    @property
    def goals(self) -> tuple[Goal, ...]:
        return tuple(self._goals.values())
    def add(self, goal: Goal) -> None:
        if not isinstance(goal, Goal):
            raise TypeError("goal must be a Goal")
        if goal.goal_id not in self._goals and len(self._goals) >= self.capacity:
            raise OverflowError("goal capacity reached")
        self._goals[goal.goal_id] = goal
    def update_status(self, goal_id: str, status: GoalStatus) -> Goal:
        if goal_id not in self._goals:
            raise KeyError(goal_id)
        if not isinstance(status, GoalStatus):
            raise TypeError("status must be a GoalStatus")
        updated = replace(self._goals[goal_id], status=status)
        self._goals[goal_id] = updated
        return updated
    def prioritize(self, *, now: float | None = None) -> tuple[tuple[Goal, float], ...]:
        timestamp = time.time() if now is None else now
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
            raise ValueError("now must be a finite timestamp")
        completed = {goal.goal_id for goal in self._goals.values() if goal.status is GoalStatus.COMPLETED}
        ranked: list[tuple[Goal, float]] = []
        for goal in self._goals.values():
            if goal.status is not GoalStatus.PENDING or any(dep not in completed for dep in goal.dependencies):
                continue
            deadline_pressure = 0.0
            if goal.deadline_at is not None:
                remaining = goal.deadline_at - timestamp
                deadline_pressure = 1.0 if remaining <= 0 else 1.0 / (1.0 + remaining / 3600.0)
            score = 0.35 * goal.importance + 0.30 * goal.urgency + 0.20 * goal.relevance + 0.15 * deadline_pressure
            ranked.append((goal, score))
        ranked.sort(key=lambda item: (-item[1], item[0].goal_id))
        return tuple(ranked)
