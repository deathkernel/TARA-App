"""Forward-mode automatic differentiation tests."""

import math
import unittest

from tara_app.mathematics import (
    DualNumber,
    automatic_derivative,
    automatic_gradient,
    cos,
    exp,
    log,
    sin,
    sqrt,
    tanh,
    value_and_gradient,
)


class TestSN86AutomaticDifferentiation(unittest.TestCase):
    def test_arithmetic_chain_rule(self):
        value, derivatives = value_and_gradient(
            lambda x: x[0] * x[0] + 3 * x[0] * x[1] + x[1] ** 3,
            (2.0, 4.0),
        )
        self.assertAlmostEqual(value, 92.0)
        self.assertAlmostEqual(derivatives[0], 16.0)
        self.assertAlmostEqual(derivatives[1], 54.0)

    def test_unary_functions(self):
        x = DualNumber.variable(0.5, 0, 1)
        self.assertAlmostEqual(exp(x).derivatives[0], math.exp(0.5))
        self.assertAlmostEqual(log(x).derivatives[0], 2.0)
        self.assertAlmostEqual(sin(x).derivatives[0], math.cos(0.5))
        self.assertAlmostEqual(cos(x).derivatives[0], -math.sin(0.5))
        self.assertAlmostEqual(tanh(x).derivatives[0], 1 - math.tanh(0.5) ** 2)
        self.assertAlmostEqual(sqrt(x).derivatives[0], 1 / (2 * math.sqrt(0.5)))

    def test_automatic_derivative_matches_analytical_result(self):
        self.assertAlmostEqual(
            automatic_derivative(lambda x: x**3 + 2 * x, 3.0),
            29.0,
        )

    def test_multivariable_gradient(self):
        result = automatic_gradient(
            lambda point: sin(point[0]) + point[1] * point[1],
            (0.0, 3.0),
        )
        self.assertAlmostEqual(result[0], 1.0)
        self.assertAlmostEqual(result[1], 6.0)

    def test_scalar_constant_has_zero_gradient(self):
        self.assertEqual(automatic_gradient(lambda point: 7.0, (1, 2)), (0.0, 0.0))

    def test_invalid_dimensions_and_domains_are_rejected(self):
        with self.assertRaises(ValueError):
            DualNumber.variable(1.0, 2, 2)
        with self.assertRaises(ValueError):
            log(DualNumber.variable(0.0, 0, 1))
        with self.assertRaises(ZeroDivisionError):
            DualNumber.variable(1.0, 0, 1) / 0.0


if __name__ == "__main__":
    unittest.main()
