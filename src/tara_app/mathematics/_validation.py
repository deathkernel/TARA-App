"""Shared validation helpers for deterministic numerical routines."""

from __future__ import annotations

import math
from collections.abc import Sequence


def finite_number(value: float, name: str = "value") -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def vector_values(values: Sequence[float], name: str = "vector") -> tuple[float, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be a sequence of real numbers")
    if not values:
        raise ValueError(f"{name} must not be empty")
    return tuple(finite_number(value, f"{name}[{index}]") for index, value in enumerate(values))


def matrix_values(
    values: Sequence[Sequence[float]], name: str = "matrix"
) -> tuple[tuple[float, ...], ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be a sequence of rows")
    if not values:
        raise ValueError(f"{name} must not be empty")
    rows = tuple(vector_values(row, f"{name}[{index}]") for index, row in enumerate(values))
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError(f"{name} must be rectangular")
    return rows
