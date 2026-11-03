"""Deterministic fail-closed boundary for optional external guardrail evaluators."""
from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass

@dataclass(frozen=True)
class GuardrailDecision:
    allowed: bool
    reason: str

class OptionalGuardrail:
    def __init__(self, evaluate: Callable[[str], bool] | None = None, *, fail_closed: bool = True) -> None:
        if type(fail_closed) is not bool:
            raise ValueError("fail_closed must be boolean")
        self._evaluate, self._fail_closed = evaluate, fail_closed

    def check(self, text: str) -> GuardrailDecision:
        if not isinstance(text, str):
            return GuardrailDecision(False, "invalid_input")
        if self._evaluate is None:
            return GuardrailDecision(not self._fail_closed, "evaluator_unavailable")
        try:
            result = self._evaluate(text)
        except Exception:
            return GuardrailDecision(not self._fail_closed, "evaluation_failed")
        if type(result) is not bool:
            return GuardrailDecision(not self._fail_closed, "invalid_evaluator_result")
        return GuardrailDecision(result, "allowed" if result else "blocked")
