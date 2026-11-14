"""Small, deterministic spiking-neural primitives for the TN-86 runtime.

This package is a software-scale research foundation. It does not attempt to
simulate the human brain's full neuron count or claim biological equivalence.
"""

from .network import SpikingNetwork
from .neurons.lif import LIFNeuron
from .synapses.connection import Synapse

__all__ = ["LIFNeuron", "SpikingNetwork", "Synapse"]
