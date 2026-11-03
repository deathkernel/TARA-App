"""Optional local media adapter boundaries without mandatory ML dependencies."""
from __future__ import annotations
from collections.abc import Callable
from typing import Any

class MediaAdapterUnavailable(RuntimeError):
    pass

class LocalTranscriptionAdapter:
    def __init__(self, transcribe: Callable[[bytes], str] | None = None, *, max_bytes: int = 25_000_000) -> None:
        if type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("max_bytes must be positive")
        self._transcribe, self._max_bytes = transcribe, max_bytes

    def run(self, audio: bytes) -> str:
        if self._transcribe is None:
            raise MediaAdapterUnavailable("local transcription backend is not configured")
        if not isinstance(audio, bytes) or not audio or len(audio) > self._max_bytes:
            raise ValueError("audio must be non-empty bytes within the configured size limit")
        result = self._transcribe(audio)
        if not isinstance(result, str):
            raise MediaAdapterUnavailable("transcription backend returned an invalid result")
        return result

class ImageTextSimilarityAdapter:
    """CLIP-like scorer injected by caller; no image uploads or model loads happen here."""
    def __init__(self, score: Callable[[Any, str], float] | None = None) -> None:
        self._score = score

    def run(self, image: Any, text: str) -> float:
        if self._score is None:
            raise MediaAdapterUnavailable("image/text similarity backend is not configured")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be non-empty")
        result = self._score(image, text)
        if isinstance(result, bool) or not isinstance(result, (int, float)):
            raise MediaAdapterUnavailable("similarity backend returned a non-numeric score")
        return float(result)
