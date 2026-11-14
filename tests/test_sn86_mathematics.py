"""Correctness and boundary tests for SN-86 mathematical services."""

import math
import unittest

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


class TestSN86Mathematics(unittest.TestCase):
    def assertTupleAlmostEqual(self, actual, expected, places=7):
        self.assertEqual(len(actual), len(expected))
        for left, right in zip(actual, expected):
            self.assertAlmostEqual(left, right, places=places)

    def test_vector_operations_are_deterministic(self):
        self.assertEqual(vector_add((1, 2), (3, 4)), (4.0, 6.0))
        self.assertEqual(vector_subtract((4, 2), (1, 5)), (3.0, -3.0))
        self.assertEqual(vector_scale((1, -2), 3), (3.0, -6.0))
        self.assertEqual(dot((1, 2, 3), (4, 5, 6)), 32.0)
        self.assertEqual(norm((3, 4)), 5.0)
        self.assertTupleAlmostEqual(normalize((3, 4)), (0.6, 0.8))

    def test_vector_dimension_and_zero_norm_are_rejected(self):
        with self.assertRaises(ValueError):
            dot((1, 2), (1,))
        with self.assertRaises(ValueError):
            normalize((0, 0))

    def test_matrix_operations_and_linear_solver(self):
        self.assertEqual(
            matrix_transpose(((1, 2, 3), (4, 5, 6))),
            ((1.0, 4.0), (2.0, 5.0), (3.0, 6.0)),
        )
        self.assertEqual(
            matrix_multiply(((1, 2), (3, 4)), ((2, 0), (1, 2))),
            ((4.0, 4.0), (10.0, 8.0)),
        )
        self.assertTupleAlmostEqual(
            solve_linear_system(((3, 2), (1, 2)), (5, 5)),
            (0.0, 2.5),
        )

    def test_linear_solver_uses_partial_pivoting(self):
        self.assertTupleAlmostEqual(
            solve_linear_system(((0, 1), (2, 3)), (1, 5)),
            (1.0, 1.0),
        )

    def test_singular_and_invalid_matrices_are_rejected(self):
        with self.assertRaises(ValueError):
            solve_linear_system(((1, 2), (2, 4)), (1, 2))
        with self.assertRaises(ValueError):
            matrix_multiply(((1, 2),), ((1, 2),))

    def test_descriptive_statistics(self):
        self.assertEqual(mean((1, 2, 3, 4)), 2.5)
        self.assertEqual(median((4, 1, 3, 2)), 2.5)
        self.assertAlmostEqual(quantile((1, 2, 3, 4), 0.25), 1.75)
        self.assertAlmostEqual(variance((1, 2, 3, 4)), 1.25)
        self.assertAlmostEqual(variance((1, 2, 3, 4), sample=True), 5 / 3)
        self.assertAlmostEqual(standard_deviation((1, 2, 3, 4)), math.sqrt(1.25))

    def test_running_statistics_match_batch_statistics_and_merge(self):
        first = RunningStatistics()
        second = RunningStatistics()
        for value in (1, 2):
            first.update(value)
        for value in (3, 4):
            second.update(value)
        first.merge(second)
        self.assertEqual(first.count, 4)
        self.assertAlmostEqual(first.average, mean((1, 2, 3, 4)))
        self.assertAlmostEqual(first.variance(), variance((1, 2, 3, 4)))
        self.assertAlmostEqual(
            first.variance(sample=True),
            variance((1, 2, 3, 4), sample=True),
        )

    def test_running_statistics_reject_empty_and_invalid_updates(self):
        with self.assertRaises(ValueError):
            RunningStatistics().variance()
        with self.assertRaises(ValueError):
            RunningStatistics().update(math.inf)
        with self.assertRaises(ValueError):
            RunningStatistics().variance(sample=True)

    def test_covariance_and_correlation(self):
        self.assertAlmostEqual(covariance((1, 2, 3), (2, 4, 6)), 4 / 3)
        self.assertAlmostEqual(correlation((1, 2, 3), (2, 4, 6)), 1.0)
        self.assertAlmostEqual(correlation((1, 2, 3), (6, 4, 2)), -1.0)

    def test_statistics_reject_undefined_inputs(self):
        with self.assertRaises(ValueError):
            variance((1,), sample=True)
        with self.assertRaises(ValueError):
            correlation((1, 1), (2, 3))
        with self.assertRaises(ValueError):
            quantile((1, 2), 1.1)

    def test_probability_transforms_are_stable(self):
        self.assertAlmostEqual(sigmoid(1000), 1.0)
        self.assertAlmostEqual(sigmoid(-1000), 0.0)
        probabilities = softmax((1000, 1001, 1002))
        self.assertAlmostEqual(math.fsum(probabilities), 1.0)
        self.assertGreater(probabilities[2], probabilities[1])
        self.assertGreater(probabilities[1], probabilities[0])
        expected = 1002 + math.log(1 + math.exp(-1) + math.exp(-2))
        self.assertAlmostEqual(logsumexp((1000, 1001, 1002)), expected)

    def test_probability_metrics_and_bayes_update(self):
        self.assertAlmostEqual(entropy((0.5, 0.5), base=2), 1.0)
        self.assertAlmostEqual(bayes_update(0.2, 0.8, 0.4), 0.4)
        self.assertAlmostEqual(gaussian_pdf(0), 1 / math.sqrt(2 * math.pi))
        self.assertAlmostEqual(
            gaussian_log_pdf(0),
            math.log(gaussian_pdf(0)),
        )

    def test_probability_inputs_are_checked(self):
        with self.assertRaises(ValueError):
            softmax((1, 2), temperature=0)
        with self.assertRaises(ValueError):
            softmax((1e308, 2), temperature=1e-308)
        with self.assertRaises(ValueError):
            entropy((0.2, 0.2))
        with self.assertRaises(ValueError):
            bayes_update(0.9, 0.9, 0.1)

    def test_numerical_calculus(self):
        self.assertAlmostEqual(derivative(lambda x: x * x, 3.0), 6.0, places=6)
        self.assertTupleAlmostEqual(
            gradient(lambda point: point[0] ** 2 + 3 * point[1] ** 2, (2, 1)),
            (4, 6),
            places=6,
        )
        self.assertAlmostEqual(
            integrate_trapezoid(lambda x: x * x, 0, 1, 1000),
            1 / 3,
            places=6,
        )
        self.assertAlmostEqual(
            integrate_simpson(lambda x: x * x, 0, 1, 10),
            1 / 3,
            places=10,
        )

    def test_simpson_requires_even_intervals(self):
        with self.assertRaises(ValueError):
            integrate_simpson(lambda x: x, 0, 1, 3)

    def test_gradient_descent_minimizes_convex_quadratic(self):
        result = gradient_descent(
            lambda point: (point[0] - 3) ** 2 + 2 * (point[1] + 1) ** 2,
            (10, 8),
        )
        self.assertTrue(result.converged)
        self.assertTupleAlmostEqual(result.point, (3, -1), places=4)
        self.assertLess(result.value, 1e-8)
        self.assertGreater(result.evaluations, result.iterations)

    def test_gradient_descent_reports_line_search_failure(self):
        objective = lambda point: 1.0 if point[0] >= 0 else 2.0
        result = gradient_descent(objective, (0.0,))
        self.assertFalse(result.converged)
        self.assertEqual(result.reason, "line_search_failed")

    def test_gradient_descent_respects_iteration_limit(self):
        result = gradient_descent(
            lambda point: (point[0] - 10) ** 2,
            (0,),
            max_iterations=1,
        )
        self.assertFalse(result.converged)
        self.assertEqual(result.reason, "maximum_iterations")

    def test_engine_facade_exposes_core_operations(self):
        engine = MathematicalEngine()
        self.assertEqual(engine.mean((2, 4)), 3.0)
        self.assertEqual(engine.sigmoid(0), 0.5)
        self.assertAlmostEqual(engine.logsumexp((0, 0)), math.log(2))
        self.assertEqual(engine.RunningStatistics().count, 0)

    def test_non_finite_values_are_rejected(self):
        for bad in (math.nan, math.inf, -math.inf):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    mean((1, bad))
                with self.assertRaises(ValueError):
                    sigmoid(bad)


if __name__ == "__main__":
    unittest.main()
