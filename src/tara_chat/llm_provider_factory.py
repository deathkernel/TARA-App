"""Environment-driven factory for optional TARA language-model providers."""
from __future__ import annotations

import os

from .ollama_provider import OllamaProvider
from .omniroute_provider import OmniRouteProvider


def provider_from_env():
    """Return the explicitly configured provider, or None when inference is disabled.

    OmniRoute owns model selection when TARA_LLM_BACKEND=omniroute. TARA keeps
    conversation context, memory, capabilities, permissions, and tool execution.
    Provider construction never downloads models or starts background services.
    """
    backend = os.getenv("TARA_LLM_BACKEND", "").strip().lower()
    if backend in {"", "none", "local"}:
        return None
    if backend in {"ollama", "llama"}:
        return OllamaProvider.from_env()
    if backend == "omniroute":
        return OmniRouteProvider.from_env()
    raise ValueError(
        f"Unsupported TARA_LLM_BACKEND {backend!r}; supported values are "
        "'omniroute', 'ollama'/'llama', or 'none'"
    )


__all__ = ["provider_from_env"]
