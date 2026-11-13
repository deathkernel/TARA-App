"""Deterministic token-budget planning for bounded model context.

The estimator is deliberately conservative and dependency-free. It is an estimate,
not a substitute for provider-reported usage or a model-specific tokenizer.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Callable, Iterable


def estimate_tokens(text: str) -> int:
    """Estimate tokens from UTF-8 bytes; never report this as provider usage."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not text:
        return 0
    return ceil(len(text.encode("utf-8")) / 3)


@dataclass(frozen=True, slots=True)
class ContextSection:
    name: str
    content: str
    priority: int
    required: bool = False


@dataclass(frozen=True, slots=True)
class ContextPlan:
    text: str
    estimated_tokens: int
    included_sections: tuple[str, ...]
    omitted_sections: tuple[str, ...]


class ContextBudgetError(ValueError):
    """Raised when required context cannot fit without truncating user input."""


def pack_context(
    sections: Iterable[ContextSection],
    *,
    max_tokens: int,
    reserve_tokens: int = 0,
    estimator: Callable[[str], int] = estimate_tokens,
) -> ContextPlan:
    """Pack complete sections by priority while preserving every required section."""
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
        raise ValueError("max_tokens must be a positive integer")
    if isinstance(reserve_tokens, bool) or not isinstance(reserve_tokens, int) or reserve_tokens < 0:
        raise ValueError("reserve_tokens must be a non-negative integer")
    available = max_tokens - reserve_tokens
    if available < 1:
        raise ContextBudgetError("output reservation leaves no input-token budget")

    items = list(sections)
    if any(not isinstance(item, ContextSection) for item in items):
        raise TypeError("sections must contain ContextSection values")
    if len({item.name for item in items}) != len(items):
        raise ValueError("context section names must be unique")

    required = [item for item in items if item.required]
    optional = sorted(
        (item for item in items if not item.required),
        key=lambda item: (-item.priority, item.name),
    )
    selected: list[ContextSection] = []
    for item in required:
        candidate = selected + [item]
        rendered = "\n\n".join(f"{part.name}:\n{part.content}" for part in candidate)
        if estimator(rendered) > available:
            raise ContextBudgetError(
                f"required context exceeds the input budget at section: {item.name}"
            )
        selected.append(item)

    omitted: list[str] = []
    for item in optional:
        candidate = selected + [item]
        rendered = "\n\n".join(f"{part.name}:\n{part.content}" for part in candidate)
        if estimator(rendered) <= available:
            selected.append(item)
        else:
            omitted.append(item.name)

    text = "\n\n".join(f"{item.name}:\n{item.content}" for item in selected)
    return ContextPlan(
        text=text,
        estimated_tokens=estimator(text),
        included_sections=tuple(item.name for item in selected),
        omitted_sections=tuple(omitted),
    )


__all__ = [
    "ContextBudgetError",
    "ContextPlan",
    "ContextSection",
    "estimate_tokens",
    "pack_context",
]
