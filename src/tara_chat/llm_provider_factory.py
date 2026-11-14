"""OmniRoute-only provider factory for SITA language-model inference."""
from __future__ import annotations

import os

from .omniroute_provider import OmniRouteProvider


def provider_from_env() -> OmniRouteProvider:
    """Create the only supported SITA Chat inference provider: OmniRoute."""
    backend = os.getenv("TARA_LLM_BACKEND", "omniroute").strip().lower()
    if backend != "omniroute":
        raise ValueError("SITA supports OmniRoute only; set TARA_LLM_BACKEND=omniroute")
    return OmniRouteProvider.from_env()


__all__ = ["provider_from_env"]
