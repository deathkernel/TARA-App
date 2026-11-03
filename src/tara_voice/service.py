"""On-device speech recognition and browser-native local read-aloud."""
from __future__ import annotations

import base64
import binascii
import os
import re
import tempfile
from pathlib import Path
from typing import Any

MODULE_ID = "voice"
CAPABILITIES = ("transcribe", "speak")
_MAX_AUDIO_BYTES = 512_000
_MAX_TEXT_CHARS = 6_000
_MEDIA_SUFFIXES = {
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/mp4": ".m4a",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/flac": ".flac",
    "audio/aac": ".aac",
}
_MODELS = frozenset({"tiny", "base", "small", "medium", "large-v3"})
_MODEL_NAME = re.compile(r"^[a-z0-9-]{1,32}$")
_LANGUAGE = re.compile(r"^[a-z]{2,3}$")
_SPEAK_PREFIX = re.compile(
    r"^\s*(?:please\s+)?(?:read(?:\s+(?:this|that|it))?|speak(?:\s+(?:this|that|it))?|say(?:\s+(?:this|that|it))?)"
    r"(?:\s+(?:aloud|out\s+loud|to\s+me))?\s*[:,-]?\s*",
    re.IGNORECASE,
)


def _transcribe(encoded: str, media_type: str, language: str | None) -> dict[str, Any]:
    if not isinstance(encoded, str) or not encoded or len(encoded) > 700_000:
        raise ValueError("audio must be bounded base64 data")
    if media_type not in _MEDIA_SUFFIXES:
        raise ValueError("audio format is not supported")
    try:
        audio = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("audio data must be valid base64") from exc
    if not audio or len(audio) > _MAX_AUDIO_BYTES:
        raise ValueError("audio input exceeds the 512 KB limit")
    if language is not None and (not isinstance(language, str) or not _LANGUAGE.fullmatch(language)):
        raise ValueError("language must be a short language code")

    model_name = os.environ.get("TARA_VOICE_MODEL", "base").strip()
    if model_name not in _MODELS or not _MODEL_NAME.fullmatch(model_name):
        raise ValueError("TARA_VOICE_MODEL must name a supported local Whisper model")
    device = os.environ.get("TARA_VOICE_DEVICE", "cpu").strip().lower()
    if device not in {"cpu", "cuda", "auto"}:
        raise ValueError("TARA_VOICE_DEVICE must be cpu, cuda, or auto")

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("local speech recognition package is unavailable") from exc

    cache_dir = Path.home() / ".tara" / "models" / "faster-whisper"
    cache_dir.mkdir(parents=True, exist_ok=True)
    compute_type = "int8" if device == "cpu" else "default"
    model = WhisperModel(model_name, device=device, compute_type=compute_type, download_root=str(cache_dir))

    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=_MEDIA_SUFFIXES[media_type], delete=False) as audio_file:
            audio_file.write(audio)
            temp_path = audio_file.name
        segments, info = model.transcribe(
            temp_path,
            language=language,
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        parts: list[str] = []
        total = 0
        for segment in segments:
            content = segment.text.strip()
            if not content:
                continue
            if total + len(content) > _MAX_TEXT_CHARS:
                content = content[: max(0, _MAX_TEXT_CHARS - total)]
            if content:
                parts.append(content)
                total += len(content)
            if total >= _MAX_TEXT_CHARS:
                break
        transcript = " ".join(parts).strip()
        return {
            "text": transcript,
            "language_code": getattr(info, "language", None),
            "duration_seconds": round(float(getattr(info, "duration", 0.0)), 2),
            "model": model_name,
            "local": True,
        }
    finally:
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except OSError:
                pass


def execute(action: str, inputs: dict[str, Any], *, approval_token: str | None = None) -> tuple[str, dict[str, Any], str | None]:
    if action == "transcribe":
        media_type = inputs.get("media_type", "audio/mpeg")
        if not isinstance(media_type, str):
            raise ValueError("audio format is invalid")
        try:
            data = _transcribe(inputs.get("audio_base64"), media_type, inputs.get("language"))
        except RuntimeError:
            return "unavailable", {}, "local speech recognition could not start or download its open model"
        except (OSError, TimeoutError):
            return "unavailable", {}, "local speech recognition is unavailable"
        except Exception:
            return "failed", {}, "local speech recognition could not process the audio"
        return "success", data, None

    if action == "speak":
        text = inputs.get("text", inputs.get("question", ""))
        if not isinstance(text, str) or not text.strip() or len(text) > 20_000:
            raise ValueError("speech text must contain 1 to 20000 characters")
        text = _SPEAK_PREFIX.sub("", text).strip()
        if not text:
            raise ValueError("include the words to read aloud")
        return "success", {
            "text": text[:_MAX_TEXT_CHARS],
            "playback": "browser_local",
            "local": True,
        }, None

    return "permission_denied", {}, "unsupported voice capability"
