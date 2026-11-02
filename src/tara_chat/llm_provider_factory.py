"""OmniRoute-only provider factory for TARA language-model inference."""
from __future__ import annotations

import os

from .omniroute_provider import OmniRouteProvider


def provider_from_env() -> OmniRouteProvider:
    """Create the only supported TARA-Chat inference provider: OmniRoute."""
    backend = os.getenv("TARA_LLM_BACKEND", "omniroute").strip().lower()
    if backend != "omniroute":
        raise ValueError("TARA supports OmniRoute only; set TARA_LLM_BACKEND=omniroute")
    api_key = os.getenv("TARA_OMNIROUTE_API_KEY", "").strip()
    if not api_key:
        try:
            from tara_app.security_vault import SecurityVault
            vault_key = SecurityVault().get_secret("TARA_OMNIROUTE_API_KEY")
            if vault_key:
                api_key = vault_key.strip()
        except Exception:
            pass
    raw_timeout = os.getenv("TARA_OMNIROUTE_TIMEOUT_SECONDS", "180").strip()
    try:
        timeout = float(raw_timeout)
    except ValueError:
        raise ValueError("TARA_OMNIROUTE_TIMEOUT_SECONDS must be numeric") from None
    return OmniRouteProvider(
        api_key=api_key,
        base_url=os.getenv("TARA_OMNIROUTE_BASE_URL", "http://127.0.0.1:20128/v1"),
        model=os.getenv("TARA_OMNIROUTE_MODEL", "auto"),
        timeout=timeout,
    )


__all__ = ["provider_from_env"]
