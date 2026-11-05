"""Deterministic helpers for the built-in MCP time server."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def current_time_payload(timezone_name: str | None = None) -> dict[str, str]:
    """Return ISO-8601 UTC and optional local time for a named zone.

    Raises ``ValueError`` for an unknown timezone name.
    """
    now_utc = datetime.now(timezone.utc)
    payload = {
        "utc_iso": now_utc.isoformat().replace("+00:00", "Z"),
        "unix_seconds": str(int(now_utc.timestamp())),
    }
    if timezone_name:
        name = timezone_name.strip()
        if not name or len(name) > 64:
            raise ValueError("timezone name must be 1–64 characters")
        try:
            zone = ZoneInfo(name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown timezone: {name}") from exc
        local = now_utc.astimezone(zone)
        payload["timezone"] = name
        payload["local_iso"] = local.isoformat()
    return payload
