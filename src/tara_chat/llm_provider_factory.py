"""Environment-driven factory for optional TARA language-model providers."""
from __future__ import annotations

import os

from .ollama_provider import OllamaProvider


def provider_from_env():
    """Return the configured provider, or None to keep TARA's built-in model.

    Set TARA_LLM_BACKEND=ollama to enable local inference. Provider construction
    is explicit and does not download models or start background services.
    """
    backend = os.getenv("TARA_LLM_BACKEND", "").strip().lower()
    if backend in {"", "none", "local"}:
        return None
    if backend in {"ollama", "llama"}:
        return OllamaProvider.from_env()
    raise ValueError(
        f"Unsupported TARA_LLM_BACKEND {backend!r}; supported values are "
        "'ollama'/'llama' or 'none'"
    )


__all__ = ["provider_from_env"]
