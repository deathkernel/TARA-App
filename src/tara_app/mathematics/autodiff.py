"""Forward-mode automatic differentiation with dual numbers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from collections.abc import Callable, Sequence

from ._validation import finite_number, vector_values


@dataclass(frozen=True, slots=True)
class DualNumber:
    """A scalar value paired with its derivative vector."""

    value: float
    derivatives: tuple[float, ...]

    def __post_init__(self) -> None:
        finite_number(self.value, "value")
        if not self.derivatives:
            raise ValueError("derivatives must contain at least one component")
        for index, derivative_value in enumerate(self.derivatives):
            finite_number(derivative_value, f"derivatives[{index}]")

    @classmethod
    def variable(cls, value: float, index: int, dimension: int) -> DualNumber:
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError("index must be an integer")
        if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension < 1:
            raise ValueError("dimension must be a positive integer")
        if not 0 <= index < dimension:
            raise ValueError("index must be within the derivative dimension")
        derivatives = tuple(1.0 if position == index else 0.0 for position in range(dimension))
        return cls(finite_number(value, "value"), derivatives)

    @classmethod
    def constant(cls, value: float, dimension: int) -> DualNumber:
        if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension < 1:
            raise ValueError("dimension must be a positive integer")
        return cls(finite_number(value, "value"), (0.0,) * dimension)

    def _coerce(self, other: float | DualNumber) -> DualNumber:
        if isinstance(other, DualNumber):
            if len(other.derivatives) != len(self.derivatives):
                raise ValueError("dual numbers must have matching derivative dimensions")
            return other
        return DualNumber.constant(finite_number(other, "operand"), len(self.derivatives))

    def __add__(self, other: float | DualNumber) -> DualNumber:
        right = self._coerce(other)
        return DualNumber(
            self.value + right.value,
            tuple(a + b for a, b in zip(self.derivatives, right.derivatives)),
        )

    def __radd__(self, other: float | DualNumber) -> DualNumber:
        return self + other

    def __sub__(self, other: float | DualNumber) -> DualNumber:
        right = self._coerce(other)
        return DualNumber(
            self.value - right.value,
            tuple(a - b for a, b in zip(self.derivatives, right.derivatives)),
        )

    def __rsub__(self, other: float | DualNumber) -> DualNumber:
        return self._coerce(other) - self

    def __mul__(self, other: float | DualNumber) -> DualNumber:
        right = self._coerce(other)
        return DualNumber(
            self.value * right.value,
            tuple(
                left_derivative * right.value + self.value * right_derivative
                for left_derivative, right_derivative in zip(
                    self.derivatives, right.derivatives
                )
            ),
        )

    def __rmul__(self, other: float | DualNumber) -> DualNumber:
        return self * other

    def __truediv__(self, other: float | DualNumber) -> DualNumber:
        right = self._coerce(other)
        if right.value == 0:
            raise ZeroDivisionError("dual division by zero")
        denominator = right.value * right.value
        return DualNumber(
            self.value / right.value,
            tuple(
                (left_derivative * right.value - self.value * right_derivative)
                / denominator
                for left_derivative, right_derivative in zip(
                    self.derivatives, right.derivatives
                )
            ),
        )

    def __rtruediv__(self, other: float | DualNumber) -> DualNumber:
        return self._coerce(other) / self

    def __neg__(self) -> DualNumber:
        return DualNumber(-self.value, tuple(-value for value in self.derivatives))

    def __pow__(self, exponent: float) -> DualNumber:
        power = finite_number(exponent, "exponent")
        if self.value == 0.0 and power < 1.0:
            raise ValueError("derivative is undefined for this power at zero")
        result = self.value**power
        derivative_factor = 0.0 if power == 0.0 else power * self.value ** (power - 1.0)
        return DualNumber(
            finite_number(result, "power result"),
            tuple(
                finite_number(derivative_factor * value, "power derivative")
                for value in self.derivatives
            ),
        )


def exp(value: DualNumber) -> DualNumber:
    result = finite_number(math.exp(value.value), "exponential result")
    return DualNumber(result, tuple(result * item for item in value.derivatives))


def log(value: DualNumber) -> DualNumber:
    if value.value <= 0:
        raise ValueError("logarithm requires a positive value")
    return DualNumber(
        math.log(value.value),
        tuple(item / value.value for item in value.derivatives),
    )


def sin(value: DualNumber) -> DualNumber:
    return DualNumber(
        math.sin(value.value),
        tuple(math.cos(value.value) * item for item in value.derivatives),
    )


def cos(value: DualNumber) -> DualNumber:
    return DualNumber(
        math.cos(value.value),
        tuple(-math.sin(value.value) * item for item in value.derivatives),
    )


def tanh(value: DualNumber) -> DualNumber:
    result = math.tanh(value.value)
    factor = 1.0 - result * result
    return DualNumber(result, tuple(factor * item for item in value.derivatives))


def sqrt(value: DualNumber) -> DualNumber:
    if value.value < 0:
        raise ValueError("square root requires a non-negative value")
    result = math.sqrt(value.value)
    if result == 0.0:
        if any(value.derivatives):
            raise ValueError("square-root derivative is undefined at zero")
        return DualNumber(0.0, (0.0,) * len(value.derivatives))
    return DualNumber(
        result,
        tuple(item / (2.0 * result) for item in value.derivatives),
    )


def value_and_gradient(
    function: Callable[[tuple[DualNumber, ...]], DualNumber | float],
    point: Sequence[float],
) -> tuple[float, tuple[float, ...]]:
    """Evaluate a scalar function and its exact forward-mode gradient."""
    values = vector_values(point, "point")
    variables = tuple(
        DualNumber.variable(value, index, len(values))
        for index, value in enumerate(values)
    )
    result = function(variables)
    if isinstance(result, DualNumber):
        if len(result.derivatives) != len(values):
            raise ValueError("function result has an invalid derivative dimension")
        return result.value, result.derivatives
    return finite_number(result, "function result"), (0.0,) * len(values)


def automatic_gradient(
    function: Callable[[tuple[DualNumber, ...]], DualNumber | float],
    point: Sequence[float],
) -> tuple[float, ...]:
    return value_and_gradient(function, point)[1]


def automatic_derivative(
    function: Callable[[DualNumber], DualNumber | float],
    point: float,
) -> float:
    return automatic_gradient(lambda values: function(values[0]), (point,))[0]
