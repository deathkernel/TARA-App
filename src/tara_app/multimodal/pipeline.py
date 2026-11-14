"""Bounded adapters from existing TARA specialists to cognitive observations."""
from __future__ import annotations

import math
import time
from collections.abc import Mapping, Sequence
from typing import Callable
from uuid import uuid4

from tara_app.cognition.models import AttentionFeatures, ContextItem

from .models import Modality, MultimodalObservation


class MultimodalInputPipeline:
    """Normalize specialist outputs without retaining source media or persisting memory."""

    MAX_BATCH_ITEMS = 16
    MAX_BATCH_CHARS = 80_000

    def __init__(self, *, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock

    def from_text(self, text: str, *, source: str = "text", confidence: float = 1.0) -> MultimodalObservation:
        return self._create(Modality.TEXT, text, source, confidence)

    def from_voice_result(self, result: Mapping[str, object]) -> MultimodalObservation:
        data = self._successful_data(result, "voice")
        if data.get("local") is not True:
            raise ValueError("voice result must originate from the local speech specialist")
        text = data.get("text")
        if not isinstance(text, str):
            raise ValueError("voice result is missing transcript text")
        attributes = []
        language = data.get("language_code")
        if isinstance(language, str) and len(language) <= 12:
            attributes.append(("language_code", language))
        model = data.get("model")
        if isinstance(model, str) and len(model) <= 64:
            attributes.append(("model", model))
        return self._create(Modality.VOICE_TRANSCRIPT, text, "tara_voice", 0.85, attributes=tuple(attributes))

    def from_vision_result(self, result: Mapping[str, object]) -> MultimodalObservation:
        data = self._successful_data(result, "vision")
        if data.get("provider") != "omniroute":
            raise ValueError("vision result must use the configured OmniRoute specialist")
        text = data.get("text")
        if not isinstance(text, str):
            raise ValueError("vision result is missing analysis text")
        attributes = [("provider", "omniroute")]
        model = data.get("model")
        if isinstance(model, str) and len(model) <= 64:
            attributes.append(("model", model))
        if data.get("images_sent_to_remote") is True:
            attributes.append(("media_routed", "through_omniroute"))
        return self._create(Modality.IMAGE_ANALYSIS, text, "tara_vision", 0.75, attributes=tuple(attributes))

    def to_context_items(self, observations: Sequence[MultimodalObservation]) -> tuple[ContextItem, ...]:
        if isinstance(observations, (str, bytes)) or len(observations) > self.MAX_BATCH_ITEMS:
            raise ValueError("multimodal batch exceeds the item limit")
        total_chars = 0
        seen: set[str] = set()
        items: list[ContextItem] = []
        for observation in observations:
            if not isinstance(observation, MultimodalObservation):
                raise TypeError("all batch entries must be MultimodalObservation values")
            if observation.observation_id in seen:
                raise ValueError("observation IDs must be unique within a batch")
            seen.add(observation.observation_id)
            total_chars += len(observation.content)
            if total_chars > self.MAX_BATCH_CHARS:
                raise ValueError("multimodal batch exceeds the text limit")
            relevance = {
                Modality.TEXT: 0.80,
                Modality.VOICE_TRANSCRIPT: 0.75,
                Modality.IMAGE_ANALYSIS: 0.70,
            }[observation.modality]
            items.append(ContextItem(
                item_id=observation.observation_id,
                content=observation.content,
                source=f"multimodal:{observation.source}",
                features=AttentionFeatures(
                    relevance=relevance, importance=0.5, recency=1.0,
                    salience=0.6, confidence=observation.confidence,
                ),
            ))
        return tuple(items)

    def _create(
        self, modality: Modality, content: str, source: str, confidence: float,
        *, attributes: tuple[tuple[str, str], ...] = (),
    ) -> MultimodalObservation:
        if not isinstance(content, str):
            raise ValueError("specialist output must contain text")
        return MultimodalObservation(
            observation_id=uuid4().hex, modality=modality, content=content.strip(),
            source=source, confidence=confidence, created_at=self._timestamp(),
            attributes=attributes,
        )

    def _timestamp(self) -> float:
        value = self._clock()
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("clock must return a finite non-negative timestamp")
        return float(value)

    @staticmethod
    def _successful_data(result: Mapping[str, object], module: str) -> Mapping[str, object]:
        if not isinstance(result, Mapping) or result.get("status") != "success":
            raise ValueError(f"{module} specialist result is not successful")
        data = result.get("data")
        if not isinstance(data, Mapping):
            raise ValueError(f"{module} specialist result has invalid data")
        return data
