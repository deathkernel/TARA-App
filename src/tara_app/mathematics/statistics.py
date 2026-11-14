"""Descriptive and online statistics with explicit sample conventions."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

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


@dataclass(slots=True)
class RunningStatistics:
    """Constant-memory online mean and variance using Welford's algorithm."""

    count: int = 0
    average: float = 0.0
    _sum_squared_deviations: float = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.count, bool) or not isinstance(self.count, int) or self.count < 0:
            raise ValueError("count must be a non-negative integer")
        self.average = finite_number(self.average, "average")
        self._sum_squared_deviations = finite_number(
            self._sum_squared_deviations, "sum_squared_deviations"
        )
        if self._sum_squared_deviations < 0:
            raise ValueError("sum_squared_deviations cannot be negative")
        if self.count == 0 and (self.average != 0.0 or self._sum_squared_deviations != 0.0):
            raise ValueError("empty statistics must start at zero")

    def update(self, value: float) -> None:
        observation = finite_number(value, "value")
        self.count += 1
        delta = observation - self.average
        self.average += delta / self.count
        delta_after_update = observation - self.average
        self._sum_squared_deviations += delta * delta_after_update

    def merge(self, other: RunningStatistics) -> None:
        if not isinstance(other, RunningStatistics):
            raise TypeError("other must be RunningStatistics")
        if other.count == 0:
            return
        if self.count == 0:
            self.count = other.count
            self.average = other.average
            self._sum_squared_deviations = other._sum_squared_deviations
            return
        combined_count = self.count + other.count
        delta = other.average - self.average
        self._sum_squared_deviations += (
            other._sum_squared_deviations
            + delta * delta * self.count * other.count / combined_count
        )
        self.average += delta * other.count / combined_count
        self.count = combined_count

    def variance(self, sample: bool = False) -> float:
        if not isinstance(sample, bool):
            raise TypeError("sample must be a boolean")
        if sample and self.count < 2:
            raise ValueError("sample variance requires at least two observations")
        if self.count == 0:
            raise ValueError("variance is undefined for empty statistics")
        denominator = self.count - 1 if sample else self.count
        return self._sum_squared_deviations / denominator

    def standard_deviation(self, sample: bool = False) -> float:
        return math.sqrt(self.variance(sample))
