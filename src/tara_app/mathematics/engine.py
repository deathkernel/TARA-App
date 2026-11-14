"""High-level façade for TN-86 mathematical services."""

from __future__ import annotations

from .calculus import derivative, gradient, integrate_simpson, integrate_trapezoid
from .linear_algebra import dot, matrix_multiply, norm, solve_linear_system
from .optimization import OptimizationResult, gradient_descent
from .probability import bayes_update, entropy, sigmoid, softmax
from .statistics import correlation, covariance, mean, median, quantile, variance


class MathematicalEngine:
    """Expose deterministic mathematical operations behind one stable API.

    The façade deliberately has no hidden state, random sampling, network calls,
    model inference, or automatic execution. Callers choose each operation and
    retain responsibility for interpreting units and domain assumptions.
    """

    mean = staticmethod(mean)
    median = staticmethod(median)
    variance = staticmethod(variance)
    covariance = staticmethod(covariance)
    correlation = staticmethod(correlation)
    quantile = staticmethod(quantile)
    dot = staticmethod(dot)
    norm = staticmethod(norm)
    matrix_multiply = staticmethod(matrix_multiply)
    solve_linear_system = staticmethod(solve_linear_system)
    sigmoid = staticmethod(sigmoid)
    softmax = staticmethod(softmax)
    entropy = staticmethod(entropy)
    bayes_update = staticmethod(bayes_update)
    derivative = staticmethod(derivative)
    gradient = staticmethod(gradient)
    integrate_trapezoid = staticmethod(integrate_trapezoid)
    integrate_simpson = staticmethod(integrate_simpson)
    gradient_descent = staticmethod(gradient_descent)


__all__ = ["MathematicalEngine", "OptimizationResult", "gradient_descent"]
