"""Bounded, explicit synaptic learning mechanisms for TN-86."""

from .engine import LearningEngine
from .rules import HebbianRule, STDPConfig

__all__ = ["HebbianRule", "LearningEngine", "STDPConfig"]
