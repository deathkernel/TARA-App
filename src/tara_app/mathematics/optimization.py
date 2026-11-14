"""Bounded gradient descent with backtracking and convergence diagnostics."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ._validation import finite_number, vector_values
from .calculus import gradient
from .linear_algebra import norm, vector_subtract


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    point: tuple[float, ...]
    value: float
    iterations: int
    converged: bool
    gradient_norm: float
    evaluations: int
    reason: str


def gradient_descent(
    objective: Callable[[tuple[float, ...]], float],
    initial_point: Sequence[float],
    learning_rate: float = 0.1,
    tolerance: float = 1e-6,
    max_iterations: int = 1000,
    finite_difference_step: float = 1e-5,
    backtracking: bool = True,
) -> OptimizationResult:
    """Minimize a differentiable scalar objective using finite-difference gradients.

    Armijo-style backtracking reduces the step when a candidate does not lower
    the objective. This is a local optimizer; it does not guarantee a global
    minimum for non-convex objectives.
    """
    point = vector_values(initial_point, "initial_point")
    rate = finite_number(learning_rate, "learning_rate")
    threshold = finite_number(tolerance, "tolerance")
    diff_step = finite_number(finite_difference_step, "finite_difference_step")
    if rate <= 0 or threshold <= 0 or diff_step <= 0:
        raise ValueError("learning_rate, tolerance and finite_difference_step must be positive")
    if isinstance(max_iterations, bool) or not isinstance(max_iterations, int) or max_iterations < 1:
        raise ValueError("max_iterations must be a positive integer")
    if not isinstance(backtracking, bool):
        raise TypeError("backtracking must be a boolean")

    current = finite_number(objective(point), "objective result")
    evaluations = 1
    current_point = point
    current_gradient_norm = math.inf

    for iteration in range(max_iterations + 1):
        current_gradient = gradient(objective, current_point, diff_step)
        evaluations += 2 * len(current_point)
        current_gradient_norm = norm(current_gradient)
        if current_gradient_norm <= threshold:
            return OptimizationResult(current_point, current, iteration, True, current_gradient_norm, evaluations, "gradient_tolerance")

        if iteration == max_iterations:
            break

        step_size = rate
        accepted = False
        candidate_value = current
        candidate_point = current_point
        directional_scale = current_gradient_norm * current_gradient_norm
        attempts = 30 if backtracking else 1
        for _ in range(attempts):
            candidate_point = vector_subtract(
                current_point,
                tuple(step_size * component for component in current_gradient),
            )
            candidate_value = finite_number(objective(candidate_point), "objective result")
            evaluations += 1
            sufficient_decrease = current - 1e-4 * step_size * directional_scale
            if candidate_value <= sufficient_decrease or not backtracking:
                accepted = candidate_value < current
                if accepted:
                    break
            step_size *= 0.5

        if not accepted:
            return OptimizationResult(current_point, current, iteration, False, current_gradient_norm, evaluations, "line_search_failed")
        current_point, current = candidate_point, candidate_value

    return OptimizationResult(current_point, current, max_iterations, False, current_gradient_norm, evaluations, "maximum_iterations")
