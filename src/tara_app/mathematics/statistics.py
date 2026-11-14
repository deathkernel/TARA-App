"""Descriptive statistics with explicit population/sample conventions."""

from __future__ import annotations

import math
from collections.abc import Sequence

from ._validation import finite_number, vector_values


def mean(values: Sequence[float]) -> float:
    data = vector_values(values)
    return math.fsum(data) / len(data)


def median(values: Sequence[float]) -> float:
    data = sorted(vector_values(values))
    middle = len(data) // 2
    if len(data) % 2:
        return data[middle]
    return (data[middle - 1] + data[middle]) / 2.0


def quantile(values: Sequence[float], probability: float) -> float:
    """Return a linearly interpolated quantile using the (n-1)*p convention."""
    data = sorted(vector_values(values))
    p = finite_number(probability, "probability")
    if not 0.0 <= p <= 1.0:
        raise ValueError("probability must be in [0, 1]")
    position = (len(data) - 1) * p
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return data[lower]
    fraction = position - lower
    return data[lower] + fraction * (data[upper] - data[lower])


def variance(values: Sequence[float], sample: bool = False) -> float:
    data = vector_values(values)
    if not isinstance(sample, bool):
        raise TypeError("sample must be a boolean")
    if sample and len(data) < 2:
        raise ValueError("sample variance requires at least two observations")
    center = math.fsum(data) / len(data)
    denominator = len(data) - 1 if sample else len(data)
    return math.fsum((value - center) ** 2 for value in data) / denominator


def standard_deviation(values: Sequence[float], sample: bool = False) -> float:
    return math.sqrt(variance(values, sample))


def covariance(left: Sequence[float], right: Sequence[float], sample: bool = False) -> float:
    a, b = vector_values(left, "left"), vector_values(right, "right")
    if len(a) != len(b):
        raise ValueError("paired observations must have equal lengths")
    if not isinstance(sample, bool):
        raise TypeError("sample must be a boolean")
    if sample and len(a) < 2:
        raise ValueError("sample covariance requires at least two observations")
    center_a, center_b = math.fsum(a) / len(a), math.fsum(b) / len(b)
    denominator = len(a) - 1 if sample else len(a)
    return math.fsum((x - center_a) * (y - center_b) for x, y in zip(a, b)) / denominator


def correlation(left: Sequence[float], right: Sequence[float]) -> float:
    a, b = vector_values(left, "left"), vector_values(right, "right")
    if len(a) != len(b):
        raise ValueError("paired observations must have equal lengths")
    std_a, std_b = standard_deviation(a), standard_deviation(b)
    if std_a == 0.0 or std_b == 0.0:
        raise ValueError("correlation is undefined for a constant variable")
    result = covariance(a, b) / (std_a * std_b)
    return max(-1.0, min(1.0, result))
