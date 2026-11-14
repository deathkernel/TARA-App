"""Leaky integrate-and-fire neuron with exact passive membrane integration."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class LIFNeuron:
    """A single leaky integrate-and-fire neuron.

    Time values are milliseconds. Current and resistance use consistent,
    caller-defined units. The membrane equation is integrated analytically
    over each constant-current time step:

        V(t + dt) = V_inf + (V(t) - V_inf) * exp(-dt / tau)
        V_inf = V_rest + R * I

    This is a useful computational neuron model, not a detailed biological
    neuron simulation.
    """

    resting_potential: float = -65.0
    threshold: float = -50.0
    reset_potential: float = -65.0
    membrane_time_constant_ms: float = 20.0
    resistance: float = 1.0
    refractory_period_ms: float = 2.0
    voltage: float | None = None
    refractory_remaining_ms: float = 0.0

    def __post_init__(self) -> None:
        values = (
            self.resting_potential,
            self.threshold,
            self.reset_potential,
            self.membrane_time_constant_ms,
            self.resistance,
            self.refractory_period_ms,
            self.refractory_remaining_ms,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("neuron parameters must be finite")
        if self.membrane_time_constant_ms <= 0:
            raise ValueError("membrane_time_constant_ms must be positive")
        if self.resistance <= 0:
            raise ValueError("resistance must be positive")
        if self.refractory_period_ms < 0 or self.refractory_remaining_ms < 0:
            raise ValueError("refractory periods cannot be negative")
        if self.threshold <= self.reset_potential:
            raise ValueError("threshold must be greater than reset_potential")
        if self.voltage is None:
            self.voltage = self.resting_potential
        elif not math.isfinite(self.voltage):
            raise ValueError("voltage must be finite")

    def reset(self) -> None:
        """Return the neuron to its resting state."""
        self.voltage = self.resting_potential
        self.refractory_remaining_ms = 0.0

    def step(self, current: float, dt_ms: float = 1.0) -> bool:
        """Advance the neuron by one time step and report whether it spiked."""
        if not math.isfinite(current):
            raise ValueError("current must be finite")
        if not math.isfinite(dt_ms) or dt_ms <= 0:
            raise ValueError("dt_ms must be a finite positive value")

        if self.refractory_remaining_ms > 0:
            self.refractory_remaining_ms = max(
                0.0, self.refractory_remaining_ms - dt_ms
            )
            self.voltage = self.reset_potential
            return False

        equilibrium = self.resting_potential + self.resistance * current
        decay = math.exp(-dt_ms / self.membrane_time_constant_ms)
        self.voltage = equilibrium + (self.voltage - equilibrium) * decay

        if self.voltage >= self.threshold:
            self.voltage = self.reset_potential
            self.refractory_remaining_ms = self.refractory_period_ms
            return True

        return False
