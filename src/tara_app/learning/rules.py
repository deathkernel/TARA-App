"""Validated mathematical rules for synaptic plasticity."""

from __future__ import annotations

import math
from dataclasses import dataclass


def _finite_positive(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number")


@dataclass(frozen=True, slots=True)
class HebbianRule:
    """Rate-based Hebbian update: co-activity strengthens a connection."""

    learning_rate: float = 0.01

    def __post_init__(self) -> None:
        _finite_positive("learning_rate", self.learning_rate)
        if self.learning_rate > 1.0:
            raise ValueError("learning_rate must not exceed 1")


@dataclass(frozen=True, slots=True)
class STDPConfig:
    """Pair-based spike-timing-dependent plasticity parameters in milliseconds."""

    potentiation_amplitude: float = 0.01
    depression_amplitude: float = 0.012
    potentiation_tau_ms: float = 20.0
    depression_tau_ms: float = 20.0

    def __post_init__(self) -> None:
        _finite_positive("potentiation_amplitude", self.potentiation_amplitude)
        _finite_positive("depression_amplitude", self.depression_amplitude)
        _finite_positive("potentiation_tau_ms", self.potentiation_tau_ms)
        _finite_positive("depression_tau_ms", self.depression_tau_ms)
        if self.potentiation_amplitude > 1.0 or self.depression_amplitude > 1.0:
            raise ValueError("STDP amplitudes must not exceed 1")
