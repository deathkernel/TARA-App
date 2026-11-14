"""Validated directed synaptic connection definitions."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Synapse:
    """Connect a presynaptic neuron to a postsynaptic neuron.

    Positive weights are excitatory and negative weights are inhibitory.
    The current implementation delivers a spike-triggered current on the
    following simulation step; explicit conduction delays are a later phase.
    """

    pre: int
    post: int
    weight: float

    def __post_init__(self) -> None:
        if isinstance(self.pre, bool) or not isinstance(self.pre, int) or self.pre < 0:
            raise ValueError("pre must be a non-negative neuron index")
        if isinstance(self.post, bool) or not isinstance(self.post, int) or self.post < 0:
            raise ValueError("post must be a non-negative neuron index")
        if not math.isfinite(self.weight):
            raise ValueError("weight must be finite")
