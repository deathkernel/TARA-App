"""Conservative decision scoring with explicit abstention."""
from __future__ import annotations
import math
from dataclasses import dataclass
from .models import ActionOption, DecisionResult, DecisionStatus

@dataclass(frozen=True, slots=True)
class DecisionPolicy:
    minimum_score: float = 0.60
    minimum_margin: float = 0.10
    risk_penalty: float = 0.25
    def __post_init__(self) -> None:
        for name in ("minimum_score", "minimum_margin", "risk_penalty"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and in [0, 1]")

class DecisionEngine:
    """Rank options; abstain when evidence or separation is insufficient."""
    def __init__(self, policy: DecisionPolicy | None = None) -> None:
        self.policy = policy or DecisionPolicy()
    def decide(self, options: tuple[ActionOption, ...] | list[ActionOption]) -> DecisionResult:
        if not options:
            return DecisionResult(DecisionStatus.ABSTAINED, None, 0.0, 0.0, "No candidate actions were supplied.")
        if len({option.action_id for option in options}) != len(options):
            raise ValueError("action_id values must be unique")
        ranked = []
        for option in options:
            score = max(0.0, min(1.0, option.expected_utility * option.confidence * option.evidence_strength - self.policy.risk_penalty * option.risk))
            ranked.append((option, score))
        ranked.sort(key=lambda item: (-item[1], item[0].action_id))
        best_option, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = best_score - second_score
        ranked_scores = tuple((option.action_id, score) for option, score in ranked)
        if best_score < self.policy.minimum_score:
            return DecisionResult(DecisionStatus.ABSTAINED, None, best_score, margin, "Best candidate did not meet the minimum evidence-adjusted score.", ranked_scores)
        if len(ranked) > 1 and margin < self.policy.minimum_margin:
            return DecisionResult(DecisionStatus.ABSTAINED, None, best_score, margin, "Candidate scores are too close for a confident selection.", ranked_scores)
        return DecisionResult(DecisionStatus.SELECTED, best_option, best_score, margin, "Selected the highest-scoring candidate under policy; execution still requires TARA authorization.", ranked_scores)
