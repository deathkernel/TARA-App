"""Small, dependency-free vector and matrix operations."""

from __future__ import annotations

import math
from collections.abc import Sequence

from ._validation import finite_number, matrix_values, vector_values


def _same_length(left: tuple[float, ...], right: tuple[float, ...]) -> None:
    if len(left) != len(right):
        raise ValueError("vectors must have equal lengths")


def vector_add(left: Sequence[float], right: Sequence[float]) -> tuple[float, ...]:
    a, b = vector_values(left, "left"), vector_values(right, "right")
    _same_length(a, b)
    return tuple(x + y for x, y in zip(a, b))


def vector_subtract(left: Sequence[float], right: Sequence[float]) -> tuple[float, ...]:
    a, b = vector_values(left, "left"), vector_values(right, "right")
    _same_length(a, b)
    return tuple(x - y for x, y in zip(a, b))


def vector_scale(vector: Sequence[float], scalar: float) -> tuple[float, ...]:
    values = vector_values(vector)
    factor = finite_number(scalar, "scalar")
    return tuple(value * factor for value in values)


def dot(left: Sequence[float], right: Sequence[float]) -> float:
    a, b = vector_values(left, "left"), vector_values(right, "right")
    _same_length(a, b)
    return math.fsum(x * y for x, y in zip(a, b))


def norm(vector: Sequence[float]) -> float:
    values = vector_values(vector)
    return math.sqrt(math.fsum(value * value for value in values))


def normalize(vector: Sequence[float], epsilon: float = 1e-12) -> tuple[float, ...]:
    values = vector_values(vector)
    threshold = finite_number(epsilon, "epsilon")
    if threshold <= 0:
        raise ValueError("epsilon must be positive")
    magnitude = math.sqrt(math.fsum(value * value for value in values))
    if magnitude <= threshold:
        raise ValueError("cannot normalize a near-zero vector")
    return tuple(value / magnitude for value in values)


def matrix_transpose(matrix: Sequence[Sequence[float]]) -> tuple[tuple[float, ...], ...]:
    rows = matrix_values(matrix)
    return tuple(tuple(rows[row][column] for row in range(len(rows))) for column in range(len(rows[0])))


def matrix_multiply(
    left: Sequence[Sequence[float]], right: Sequence[Sequence[float]]
) -> tuple[tuple[float, ...], ...]:
    a, b = matrix_values(left, "left"), matrix_values(right, "right")
    if len(a[0]) != len(b):
        raise ValueError("left columns must equal right rows")
    columns = matrix_transpose(b)
    return tuple(
        tuple(math.fsum(x * y for x, y in zip(row, column)) for column in columns)
        for row in a
    )


def solve_linear_system(
    matrix: Sequence[Sequence[float]],
    vector: Sequence[float],
    pivot_tolerance: float = 1e-12,
) -> tuple[float, ...]:
    """Solve Ax=b with Gaussian elimination and partial pivoting.

    Raises ValueError for non-square or numerically singular systems. The
    tolerance is an absolute pivot threshold, not a condition-number estimate.
    """
    rows = matrix_values(matrix)
    values = vector_values(vector, "vector")
    tolerance = finite_number(pivot_tolerance, "pivot_tolerance")
    size = len(rows)
    if size != len(rows[0]) or len(values) != size:
        raise ValueError("matrix must be square and match vector length")
    if tolerance <= 0:
        raise ValueError("pivot_tolerance must be positive")

    augmented = [list(row) + [values[index]] for index, row in enumerate(rows)]
    for column in range(size):
        pivot_row = max(range(column, size), key=lambda index: abs(augmented[index][column]))
        pivot = augmented[pivot_row][column]
        if abs(pivot) <= tolerance:
            raise ValueError("matrix is singular or numerically ill-conditioned")
        if pivot_row != column:
            augmented[column], augmented[pivot_row] = augmented[pivot_row], augmented[column]

        pivot = augmented[column][column]
        for row in range(column + 1, size):
            factor = augmented[row][column] / pivot
            augmented[row][column] = 0.0
            for index in range(column + 1, size + 1):
                augmented[row][index] -= factor * augmented[column][index]

    solution = [0.0] * size
    for row in range(size - 1, -1, -1):
        remainder = math.fsum(
            augmented[row][column] * solution[column]
            for column in range(row + 1, size)
        )
        solution[row] = (augmented[row][size] - remainder) / augmented[row][row]
    return tuple(solution)
