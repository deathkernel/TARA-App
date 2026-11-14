"""Correctness and boundary tests for TN-86 mathematical services."""

import math

import pytest

from tara_app.mathematics import (
    MathematicalEngine,
    RunningStatistics,
    bayes_update,
    correlation,
    covariance,
    derivative,
    dot,
    entropy,
    gaussian_pdf,
    gaussian_log_pdf,
    gradient,
    gradient_descent,
    integrate_simpson,
    integrate_trapezoid,
    logsumexp,
    matrix_multiply,
    matrix_transpose,
    mean,
    median,
    norm,
    normalize,
    quantile,
    sigmoid,
    softmax,
    solve_linear_system,
    standard_deviation,
    variance,
    vector_add,
    vector_scale,
    vector_subtract,
)


def test_vector_operations_are_deterministic():
    assert vector_add((1, 2), (3, 4)) == (4.0, 6.0)
    assert vector_subtract((4, 2), (1, 5)) == (3.0, -3.0)
    assert vector_scale((1, -2), 3) == (3.0, -6.0)
    assert dot((1, 2, 3), (4, 5, 6)) == 32.0
    assert norm((3, 4)) == 5.0
    assert normalize((3, 4)) == (0.6, 0.8)


def test_vector_dimension_and_zero_norm_are_rejected():
    with pytest.raises(ValueError):
        dot((1, 2), (1,))
    with pytest.raises(ValueError):
        normalize((0, 0))


def test_matrix_operations_and_linear_solver():
    assert matrix_transpose(((1, 2, 3), (4, 5, 6))) == ((1.0, 4.0), (2.0, 5.0), (3.0, 6.0))
    assert matrix_multiply(((1, 2), (3, 4)), ((2, 0), (1, 2))) == ((4.0, 4.0), (10.0, 8.0))
    solution = solve_linear_system(((3, 2), (1, 2)), (5, 5))
    assert solution == pytest.approx((0.0, 2.5))


def test_linear_solver_uses_partial_pivoting():
    assert solve_linear_system(((0, 1), (2, 3)), (1, 5)) == pytest.approx((1.0, 1.0))


def test_singular_and_invalid_matrices_are_rejected():
    with pytest.raises(ValueError):
        solve_linear_system(((1, 2), (2, 4)), (1, 2))
    with pytest.raises(ValueError):
        matrix_multiply(((1, 2),), ((1, 2),))


def test_descriptive_statistics():
    assert mean((1, 2, 3, 4)) == 2.5
    assert median((4, 1, 3, 2)) == 2.5
    assert quantile((1, 2, 3, 4), 0.25) == pytest.approx(1.75)
    assert variance((1, 2, 3, 4)) == pytest.approx(1.25)
    assert variance((1, 2, 3, 4), sample=True) == pytest.approx(5 / 3)
    assert standard_deviation((1, 2, 3, 4)) == pytest.approx(math.sqrt(1.25))


def test_running_statistics_match_batch_statistics_and_merge():
    first = RunningStatistics()
    second = RunningStatistics()
    for value in (1, 2):
        first.update(value)
    for value in (3, 4):
        second.update(value)
    first.merge(second)
    assert first.count == 4
    assert first.average == pytest.approx(mean((1, 2, 3, 4)))
    assert first.variance() == pytest.approx(variance((1, 2, 3, 4)))
    assert first.variance(sample=True) == pytest.approx(variance((1, 2, 3, 4), sample=True))


def test_running_statistics_reject_empty_and_invalid_updates():
    with pytest.raises(ValueError):
        RunningStatistics().variance()
    with pytest.raises(ValueError):
        RunningStatistics().update(math.inf)
    with pytest.raises(ValueError):
        RunningStatistics().variance(sample=True)


def test_covariance_and_correlation():
    assert covariance((1, 2, 3), (2, 4, 6)) == pytest.approx(4 / 3)
    assert correlation((1, 2, 3), (2, 4, 6)) == pytest.approx(1.0)
    assert correlation((1, 2, 3), (6, 4, 2)) == pytest.approx(-1.0)


def test_statistics_reject_undefined_inputs():
    with pytest.raises(ValueError):
        variance((1,), sample=True)
    with pytest.raises(ValueError):
        correlation((1, 1), (2, 3))
    with pytest.raises(ValueError):
        quantile((1, 2), 1.1)


def test_probability_transforms_are_stable():
    assert sigmoid(1000) == pytest.approx(1.0)
    assert sigmoid(-1000) == pytest.approx(0.0)
    probabilities = softmax((1000, 1001, 1002))
    assert math.fsum(probabilities) == pytest.approx(1.0)
    assert probabilities[2] > probabilities[1] > probabilities[0]
    assert logsumexp((1000, 1001, 1002)) == pytest.approx(1002 + math.log(1 + math.exp(-1) + math.exp(-2)))


def test_probability_metrics_and_bayes_update():
    assert entropy((0.5, 0.5), base=2) == pytest.approx(1.0)
    assert bayes_update(0.2, 0.8, 0.4) == pytest.approx(0.4)
    assert gaussian_pdf(0) == pytest.approx(1 / math.sqrt(2 * math.pi))
    assert gaussian_log_pdf(0) == pytest.approx(math.log(gaussian_pdf(0)))


def test_probability_inputs_are_checked():
    with pytest.raises(ValueError):
        softmax((1, 2), temperature=0)
    with pytest.raises(ValueError):
        softmax((1e308, 2), temperature=1e-308)
    with pytest.raises(ValueError):
        entropy((0.2, 0.2))
    with pytest.raises(ValueError):
        bayes_update(0.9, 0.9, 0.1)


def test_numerical_calculus():
    assert derivative(lambda x: x * x, 3.0) == pytest.approx(6.0, rel=1e-7)
    assert gradient(lambda point: point[0] ** 2 + 3 * point[1] ** 2, (2, 1)) == pytest.approx((4, 6), rel=1e-7)
    assert integrate_trapezoid(lambda x: x * x, 0, 1, 1000) == pytest.approx(1 / 3, abs=1e-6)
    assert integrate_simpson(lambda x: x * x, 0, 1, 10) == pytest.approx(1 / 3)


def test_simpson_requires_even_intervals():
    with pytest.raises(ValueError):
        integrate_simpson(lambda x: x, 0, 1, 3)


def test_gradient_descent_minimizes_convex_quadratic():
    result = gradient_descent(lambda point: (point[0] - 3) ** 2 + 2 * (point[1] + 1) ** 2, (10, 8))
    assert result.converged
    assert result.point == pytest.approx((3, -1), abs=1e-4)
    assert result.value < 1e-8
    assert result.evaluations > result.iterations


def test_gradient_descent_reports_line_search_failure():
    objective = lambda point: 1.0 if point[0] >= 0 else 2.0
    result = gradient_descent(objective, (0.0,))
    assert not result.converged
    assert result.reason == "line_search_failed"


def test_gradient_descent_respects_iteration_limit():
    result = gradient_descent(lambda point: (point[0] - 10) ** 2, (0,), max_iterations=1)
    assert not result.converged
    assert result.reason == "maximum_iterations"


def test_engine_facade_exposes_core_operations():
    engine = MathematicalEngine()
    assert engine.mean((2, 4)) == 3.0
    assert engine.sigmoid(0) == 0.5
    assert engine.logsumexp((0, 0)) == pytest.approx(math.log(2))
    assert engine.RunningStatistics().count == 0


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_values_are_rejected(bad):
    with pytest.raises(ValueError):
        mean((1, bad))
    with pytest.raises(ValueError):
        sigmoid(bad)
