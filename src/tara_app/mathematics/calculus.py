"""Numerical differentiation and integration for scalar functions."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

from ._validation import finite_number, vector_values


def derivative(
    function: Callable[[float], float], point: float, step: float = 1e-5
) -> float:
    """Estimate a first derivative using a centered finite difference."""
    x, h = finite_number(point, "point"), finite_number(step, "step")
    if h <= 0:
        raise ValueError("step must be positive")
    left, right = finite_number(function(x - h), "function result"), finite_number(function(x + h), "function result")
    return (right - left) / (2.0 * h)


def gradient(
    function: Callable[[tuple[float, ...]], float],
    point: Sequence[float],
    step: float = 1e-5,
) -> tuple[float, ...]:
    """Estimate a gradient with coordinate-wise centered differences."""
    values = vector_values(point, "point")
    h = finite_number(step, "step")
    if h <= 0:
        raise ValueError("step must be positive")
    result = []
    for index in range(len(values)):
        lower, upper = list(values), list(values)
        lower[index] -= h
        upper[index] += h
        left = finite_number(function(tuple(lower)), "function result")
        right = finite_number(function(tuple(upper)), "function result")
        result.append((right - left) / (2.0 * h))
    return tuple(result)


def integrate_trapezoid(
    function: Callable[[float], float], start: float, end: float, intervals: int = 100
) -> float:
    a, b = finite_number(start, "start"), finite_number(end, "end")
    if isinstance(intervals, bool) or not isinstance(intervals, int) or intervals < 1:
        raise ValueError("intervals must be a positive integer")
    width = (b - a) / intervals
    values = [finite_number(function(a + index * width), "function result") for index in range(intervals + 1)]
    return width * (0.5 * values[0] + math.fsum(values[1:-1]) + 0.5 * values[-1])


def integrate_simpson(
    function: Callable[[float], float], start: float, end: float, intervals: int = 100
) -> float:
    a, b = finite_number(start, "start"), finite_number(end, "end")
    if isinstance(intervals, bool) or not isinstance(intervals, int) or intervals < 2 or intervals % 2:
        raise ValueError("Simpson integration requires a positive even interval count")
    width = (b - a) / intervals
    values = [finite_number(function(a + index * width), "function result") for index in range(intervals + 1)]
    odd = math.fsum(values[index] for index in range(1, intervals, 2))
    even = math.fsum(values[index] for index in range(2, intervals, 2))
    return width * (values[0] + values[-1] + 4.0 * odd + 2.0 * even) / 3.0
