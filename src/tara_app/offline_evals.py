"""Tiny offline evaluation harness; never calls hosted models or the network."""
from __future__ import annotations
from collections.abc import Callable, Iterable
from dataclasses import dataclass

@dataclass(frozen=True)
class EvalCase:
    case_id: str
    input_text: str
    expected: str

@dataclass(frozen=True)
class EvalResult:
    case_id: str
    passed: bool

def run_offline_evals(cases: Iterable[EvalCase], responder: Callable[[str], str]) -> tuple[EvalResult, ...]:
    results: list[EvalResult] = []
    seen: set[str] = set()
    for case in cases:
        if not case.case_id.strip() or case.case_id in seen:
            raise ValueError("evaluation case IDs must be non-empty and unique")
        if not isinstance(case.input_text, str) or not isinstance(case.expected, str):
            raise ValueError("evaluation inputs and expected values must be strings")
        seen.add(case.case_id)
        actual = responder(case.input_text)
        if not isinstance(actual, str):
            raise TypeError("responder must return text")
        results.append(EvalResult(case.case_id, actual == case.expected))
    return tuple(results)
