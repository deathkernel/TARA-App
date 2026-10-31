"""Environment-driven factory for optional TARA language-model providers."""
from __future__ import annotations

import os

from .ollama_provider import OllamaProvider


def provider_from_env():
    """Construct the explicitly selected provider without starting background work.

    TARA_LLM_BACKEND accepts 'ollama' or 'bharatcode'. Remote inference is
    opt-in and requires a server-side BHARATCODE_API_KEY environment variable.
    """
    backend = os.getenv("TARA_LLM_BACKEND", "").strip().lower()
    if backend in {"", "none", "local"}:
        return None
    if backend in {"ollama", "llama"}:
        return OllamaProvider.from_env()
    if backend == "bharatcode":
        from tara_app.providers.bharatcode import BharatCodeProvider
        return BharatCodeProvider.from_env()
    raise ValueError(
        f"Unsupported TARA_LLM_BACKEND {backend!r}; supported values are "
        "'ollama'/'llama', 'bharatcode', or 'none'"
    )


__all__ = ["provider_from_env"]
