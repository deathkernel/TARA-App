"""Safe, bounded synaptic plasticity and learning-state persistence."""

from __future__ import annotations

import json
import math
import os
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path

from tara_app.neural.synapses.connection import Synapse

from .rules import HebbianRule, STDPConfig


class LearningEngine:
    """Apply Hebbian and pair-based STDP updates to a fixed synapse topology.

    The sign of each connection is invariant: excitatory weights remain
    non-negative and inhibitory weights remain non-positive. Learning changes
    magnitude only and clamps it to max_weight_magnitude.
    """

    def __init__(
        self,
        synapses: Sequence[Synapse],
        *,
        hebbian: HebbianRule | None = None,
        stdp: STDPConfig | None = None,
        max_weight_magnitude: float = 5.0,
    ) -> None:
        if isinstance(max_weight_magnitude, bool) or not isinstance(max_weight_magnitude, (int, float)) or not math.isfinite(max_weight_magnitude) or max_weight_magnitude <= 0:
            raise ValueError("max_weight_magnitude must be finite and positive")
        self.hebbian = hebbian or HebbianRule()
        self.stdp = stdp or STDPConfig()
        self.max_weight_magnitude = float(max_weight_magnitude)
        self._topology = tuple(synapses)
        if any(not isinstance(item, Synapse) for item in self._topology):
            raise TypeError("synapses must contain only Synapse instances")
        if any(abs(item.weight) > self.max_weight_magnitude for item in self._topology):
            raise ValueError("initial synapse weight exceeds max_weight_magnitude")
        self._weights = [float(item.weight) for item in self._topology]

    @property
    def synapses(self) -> tuple[Synapse, ...]:
        """Return the fixed topology with current learned weights."""
        return tuple(
            replace(synapse, weight=self._weights[index])
            for index, synapse in enumerate(self._topology)
        )

    @property
    def weights(self) -> tuple[float, ...]:
        return tuple(self._weights)

    def snapshot(self) -> tuple[float, ...]:
        """Capture a rollback point for a learning transaction."""
        return tuple(self._weights)

    def restore(self, snapshot: Sequence[float]) -> None:
        """Restore a prior state after validating topology and all weights."""
        if len(snapshot) != len(self._weights):
            raise ValueError("snapshot does not match synapse topology")
        validated = [self._validate_weight(index, value) for index, value in enumerate(snapshot)]
        self._weights = validated

    def _validate_weight(self, index: int, weight: float) -> float:
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight):
            raise ValueError("weight must be a finite number")
        original = self._topology[index].weight
        if original > 0 and weight < 0 or original < 0 and weight > 0:
            raise ValueError("learning cannot reverse synapse polarity")
        if abs(weight) > self.max_weight_magnitude:
            raise ValueError("weight exceeds max_weight_magnitude")
        return float(weight)

    def _apply_delta(self, index: int, magnitude_delta: float) -> float:
        current = self._weights[index]
        polarity = 1.0 if self._topology[index].weight >= 0 else -1.0
        magnitude = min(
            self.max_weight_magnitude,
            max(0.0, abs(current) + magnitude_delta),
        )
        self._weights[index] = polarity * magnitude
        return self._weights[index]

    def apply_hebbian(
        self,
        synapse_index: int,
        *,
        pre_activity: float,
        post_activity: float,
    ) -> float:
        """Update weight from normalized pre/post activity in [0, 1]."""
        self._validate_index(synapse_index)
        for name, value in (("pre_activity", pre_activity), ("post_activity", post_activity)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        delta = self.hebbian.learning_rate * pre_activity * post_activity
        return self._apply_delta(synapse_index, delta)

    def apply_stdp(
        self,
        synapse_index: int,
        *,
        pre_spike_times_ms: Sequence[float],
        post_spike_times_ms: Sequence[float],
    ) -> float:
        """Apply all spike pairs; positive timing strengthens, negative weakens."""
        self._validate_index(synapse_index)
        if len(pre_spike_times_ms) > 512 or len(post_spike_times_ms) > 512:
            raise ValueError("at most 512 spike times are accepted per neuron")
        pre_times = self._validate_spike_times(pre_spike_times_ms)
        post_times = self._validate_spike_times(post_spike_times_ms)
        delta = 0.0
        for pre_time in pre_times:
            for post_time in post_times:
                interval = post_time - pre_time
                if interval > 0:
                    delta += self.stdp.potentiation_amplitude * math.exp(
                        -interval / self.stdp.potentiation_tau_ms
                    )
                elif interval < 0:
                    delta -= self.stdp.depression_amplitude * math.exp(
                        interval / self.stdp.depression_tau_ms
                    )
        if not math.isfinite(delta):
            raise ValueError("STDP update is not finite")
        return self._apply_delta(synapse_index, delta)

    @staticmethod
    def _validate_spike_times(values: Sequence[float]) -> tuple[float, ...]:
        times = tuple(values)
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in times
        ):
            raise ValueError("spike times must be finite numbers")
        if tuple(sorted(times)) != times:
            raise ValueError("spike times must be sorted in ascending order")
        return times

    def _validate_index(self, index: int) -> None:
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(self._weights):
            raise IndexError("synapse_index is out of range")

    def apply_to_network(self, network: object) -> None:
        """Copy learned weights into a compatible SpikingNetwork instance."""
        setter = getattr(network, "set_synapse_weight", None)
        network_synapses = getattr(network, "synapses", None)
        if not callable(setter) or network_synapses is None:
            raise TypeError("network must expose synapses and set_synapse_weight")
        if len(network_synapses) != len(self._topology):
            raise ValueError("network topology does not match learning topology")
        if any(
            current.pre != expected.pre or current.post != expected.post
            for current, expected in zip(network_synapses, self._topology)
        ):
            raise ValueError("network topology does not match learning topology")
        for index, weight in enumerate(self._weights):
            setter(index, weight)

    def save(
        self,
        path: str | Path,
        *,
        authorize_write: Callable[[], bool],
    ) -> None:
        """Persist weights atomically; caller must provide explicit approval."""
        if not callable(authorize_write) or not authorize_write():
            raise PermissionError("learning-state persistence requires approval")
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format_version": 1,
            "weights": list(self._weights),
            "topology": [
                {"pre": item.pre, "post": item.post}
                for item in self._topology
            ],
            "max_weight_magnitude": self.max_weight_magnitude,
        }
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = handle.name
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, destination)
        finally:
            if temporary_path is not None and os.path.exists(temporary_path):
                os.unlink(temporary_path)

    def load(self, path: str | Path) -> None:
        """Load state only when its exact synapse topology matches this engine."""
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("format_version") != 1:
            raise ValueError("unsupported learning-state format")
        expected_topology = [
            {"pre": item.pre, "post": item.post}
            for item in self._topology
        ]
        if payload.get("topology") != expected_topology:
            raise ValueError("learning state topology does not match")
        if payload.get("max_weight_magnitude") != self.max_weight_magnitude:
            raise ValueError("learning state weight limit does not match")
        weights = payload.get("weights")
        if not isinstance(weights, list) or len(weights) != len(self._weights):
            raise ValueError("invalid learning-state weights")
        self.restore(weights)
