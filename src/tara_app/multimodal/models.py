"""Immutable, metadata-only observations for SN-86B multimodal processing."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import StrEnum


class Modality(StrEnum):
    TEXT = "text"
    VOICE_TRANSCRIPT = "voice_transcript"
    IMAGE_ANALYSIS = "image_analysis"


_KEY = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


@dataclass(frozen=True, slots=True)
class MultimodalObservation:
    """A normalized text representation; raw audio and image bytes are never stored."""

    observation_id: str
    modality: Modality
    content: str
    source: str
    confidence: float = 1.0
    created_at: float = 0.0
    attributes: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.observation_id, str) or not self.observation_id.strip() or len(self.observation_id) > 128:
            raise ValueError("observation_id must contain 1 to 128 characters")
        if not isinstance(self.modality, Modality):
            raise TypeError("modality must be a Modality")
        if not isinstance(self.content, str) or not self.content.strip() or len(self.content) > 20_000:
            raise ValueError("content must contain 1 to 20000 characters")
        if "\x00" in self.content:
            raise ValueError("content must not contain NUL characters")
        if not isinstance(self.source, str) or not self.source.strip() or len(self.source) > 64:
            raise ValueError("source must contain 1 to 64 characters")
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)) or not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be finite and in [0, 1]")
        if isinstance(self.created_at, bool) or not isinstance(self.created_at, (int, float)) or not math.isfinite(self.created_at) or self.created_at < 0:
            raise ValueError("created_at must be a finite non-negative timestamp")
        if not isinstance(self.attributes, tuple) or len(self.attributes) > 16:
            raise ValueError("attributes must be a tuple with at most 16 entries")
        seen: set[str] = set()
        for entry in self.attributes:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise ValueError("each attribute must be a key/value pair")
            key, value = entry
            if not isinstance(key, str) or not _KEY.fullmatch(key) or key in seen:
                raise ValueError("attribute keys must be unique lowercase identifiers")
            if not isinstance(value, str) or len(value) > 256:
                raise ValueError("attribute values must be strings of at most 256 characters")
            seen.add(key)
