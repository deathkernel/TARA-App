"""Sparse, deterministic spiking network simulation."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from .neurons.lif import LIFNeuron
from .synapses.connection import Synapse


class SpikingNetwork:
    """Run a small network of LIF neurons connected by sparse synapses.

    Synaptic events are intentionally discrete: a neuron that spikes during
    one step contributes its outgoing weights as current during the next step.
    This makes event ordering deterministic and keeps the first engine small.
    """

    def __init__(self) -> None:
        self._neurons: list[LIFNeuron] = []
        self._synapses: list[Synapse] = []
        self._outgoing: dict[int, list[Synapse]] = {}
        self._last_spikes: tuple[int, ...] = ()

    @property
    def neuron_count(self) -> int:
        return len(self._neurons)

    @property
    def synapse_count(self) -> int:
        return len(self._synapses)

    @property
    def synapses(self) -> tuple[Synapse, ...]:
        return tuple(self._synapses)

    def add_neuron(self, neuron: LIFNeuron | None = None) -> int:
        """Add a neuron and return its stable index."""
        instance = neuron if neuron is not None else LIFNeuron()
        if not isinstance(instance, LIFNeuron):
            raise TypeError("neuron must be an LIFNeuron")
        index = len(self._neurons)
        self._neurons.append(instance)
        self._outgoing[index] = []
        return index

    def add_synapse(self, synapse: Synapse) -> None:
        """Add a directed connection after validating its endpoints."""
        if not isinstance(synapse, Synapse):
            raise TypeError("synapse must be a Synapse")
        if synapse.pre >= self.neuron_count or synapse.post >= self.neuron_count:
            raise ValueError("synapse endpoint does not exist")
        self._synapses.append(synapse)
        self._outgoing[synapse.pre].append(synapse)

    def set_synapse_weight(self, index: int, weight: float) -> None:
        """Replace one connection's weight without changing its topology."""
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(self._synapses):
            raise IndexError("synapse index is out of range")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight):
            raise ValueError("weight must be a finite number")
        previous = self._synapses[index]
        if previous.weight > 0 and weight < 0 or previous.weight < 0 and weight > 0:
            raise ValueError("weight update cannot reverse synapse polarity")
        updated = Synapse(pre=previous.pre, post=previous.post, weight=float(weight))
        self._synapses[index] = updated
        self._outgoing[previous.pre] = [
            updated if item is previous else item
            for item in self._outgoing[previous.pre]
        ]

    def reset(self) -> None:
        """Reset all neurons and clear pending spike events."""
        for neuron in self._neurons:
            neuron.reset()
        self._last_spikes = ()

    def step(
        self,
        external_currents: Sequence[float] | None = None,
        dt_ms: float = 1.0,
    ) -> tuple[int, ...]:
        """Advance the full network and return indices that spiked this step."""
        if not math.isfinite(dt_ms) or dt_ms <= 0:
            raise ValueError("dt_ms must be a finite positive value")

        currents = list(external_currents) if external_currents is not None else [
            0.0
        ] * self.neuron_count
        if len(currents) != self.neuron_count:
            raise ValueError("external_currents must match neuron_count")
        if any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in currents):
            raise ValueError("all external currents must be finite numbers")

        total_currents = [float(value) for value in currents]
        for pre_index in self._last_spikes:
            for synapse in self._outgoing[pre_index]:
                total_currents[synapse.post] += synapse.weight

        spikes = tuple(
            index
            for index, (neuron, current) in enumerate(
                zip(self._neurons, total_currents)
            )
            if neuron.step(current, dt_ms)
        )
        self._last_spikes = spikes
        return spikes

    def run(
        self,
        current_steps: Iterable[Sequence[float]],
        dt_ms: float = 1.0,
    ) -> tuple[tuple[int, ...], ...]:
        """Run a sequence of external-current vectors and return spike events."""
        return tuple(self.step(currents, dt_ms) for currents in current_steps)
