"""Composition entry point for the SITA application boundary."""
from __future__ import annotations

from pathlib import Path

from tara_app.application.facade import ApplicationFacade
from tara_app.runtime import RuntimeConfigurationError, create_application as create_runtime


def create_application(config_path: str | Path) -> ApplicationFacade:
    """Build configured runtime components and expose only the application facade."""
    coordinator = create_runtime(config_path)
    return ApplicationFacade(coordinator)


__all__ = ["RuntimeConfigurationError", "create_application"]
