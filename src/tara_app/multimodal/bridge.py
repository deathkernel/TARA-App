"""Explicit bridge from normalized multimodal observations to cognition."""
from __future__ import annotations

from collections.abc import Sequence

from tara_app.cognition import CognitiveCoordinator
from tara_app.cognition.models import CognitiveRequest, DecisionResult, ReasoningTrace

from .models import MultimodalObservation
from .pipeline import MultimodalInputPipeline


class MultimodalCognitiveBridge:
    """Pass transient observations into cognition; never persists or executes them."""

    def __init__(
        self,
        coordinator: CognitiveCoordinator,
        pipeline: MultimodalInputPipeline | None = None,
    ) -> None:
        self.coordinator = coordinator
        self.pipeline = pipeline or MultimodalInputPipeline()

    def process(
        self,
        request: CognitiveRequest,
        observations: Sequence[MultimodalObservation],
    ) -> tuple[DecisionResult, ReasoningTrace]:
        context_items = self.pipeline.to_context_items(observations)
        return self.coordinator.process(request, observations=context_items)
