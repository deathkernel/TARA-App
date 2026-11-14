"""TN-86 deterministic mathematical intelligence primitives."""

from .calculus import derivative, gradient, integrate_simpson, integrate_trapezoid
from .engine import MathematicalEngine
from .linear_algebra import (
    dot,
    matrix_multiply,
    matrix_transpose,
    norm,
    normalize,
    solve_linear_system,
    vector_add,
    vector_scale,
    vector_subtract,
)
from .optimization import OptimizationResult, gradient_descent
from .probability import (
    bayes_update,
    entropy,
    gaussian_pdf,
    gaussian_log_pdf,
    sigmoid,
    softmax,
)
from .statistics import (
    correlation,
    covariance,
    mean,
    median,
    quantile,
    standard_deviation,
    variance,
)

__all__ = [
    "MathematicalEngine",
    "OptimizationResult",
    "bayes_update",
    "correlation",
    "covariance",
    "derivative",
    "dot",
    "entropy",
    "gaussian_log_pdf",
    "gaussian_pdf",
    "gradient",
    "gradient_descent",
    "integrate_simpson",
    "integrate_trapezoid",
    "matrix_multiply",
    "matrix_transpose",
    "mean",
    "median",
    "norm",
    "normalize",
    "quantile",
    "sigmoid",
    "softmax",
    "solve_linear_system",
    "standard_deviation",
    "variance",
    "vector_add",
    "vector_scale",
    "vector_subtract",
]
