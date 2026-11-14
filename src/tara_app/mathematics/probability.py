"""Stable probability transforms and elementary distribution operations."""

from __future__ import annotations

import math
from collections.abc import Sequence

from ._validation import finite_number, vector_values


def sigmoid(value: float) -> float:
    x = finite_number(value)
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def softmax(values: Sequence[float], temperature: float = 1.0) -> tuple[float, ...]:
    logits = vector_values(values)
    scale = finite_number(temperature, "temperature")
    if scale <= 0:
        raise ValueError("temperature must be positive")
    scaled = tuple(value / scale for value in logits)
    maximum = max(scaled)
    exponentials = tuple(math.exp(value - maximum) for value in scaled)
    total = math.fsum(exponentials)
    return tuple(value / total for value in exponentials)


def entropy(probabilities: Sequence[float], base: float = math.e) -> float:
    values = vector_values(probabilities, "probabilities")
    log_base = finite_number(base, "base")
    if log_base <= 0 or log_base == 1:
        raise ValueError("base must be positive and different from one")
    if any(value < 0 or value > 1 for value in values):
        raise ValueError("probabilities must be in [0, 1]")
    if not math.isclose(math.fsum(values), 1.0, rel_tol=1e-9, abs_tol=1e-12):
        raise ValueError("probabilities must sum to one")
    return -math.fsum(value * math.log(value, log_base) for value in values if value > 0)


def gaussian_log_pdf(value: float, mean: float = 0.0, standard_deviation: float = 1.0) -> float:
    x = finite_number(value)
    center = finite_number(mean, "mean")
    spread = finite_number(standard_deviation, "standard_deviation")
    if spread <= 0:
        raise ValueError("standard_deviation must be positive")
    z = (x - center) / spread
    return -0.5 * z * z - math.log(spread) - 0.5 * math.log(2.0 * math.pi)


def gaussian_pdf(value: float, mean: float = 0.0, standard_deviation: float = 1.0) -> float:
    return math.exp(gaussian_log_pdf(value, mean, standard_deviation))


def bayes_update(prior: float, likelihood: float, evidence: float) -> float:
    """Return P(H|E) from P(H), P(E|H), and P(E).

    P(E) must be the marginal evidence probability, not merely P(E|H).
    """
    p_prior = finite_number(prior, "prior")
    p_likelihood = finite_number(likelihood, "likelihood")
    p_evidence = finite_number(evidence, "evidence")
    if any(value < 0 or value > 1 for value in (p_prior, p_likelihood, p_evidence)):
        raise ValueError("probabilities must be in [0, 1]")
    if p_evidence == 0:
        raise ValueError("evidence probability must be positive")
    posterior = p_likelihood * p_prior / p_evidence
    if posterior > 1.0 + 1e-12:
        raise ValueError("inputs are inconsistent with a valid posterior probability")
    return min(1.0, posterior)
