"""Bounded JSON-over-stdio CSV analysis specialist."""
from __future__ import annotations

import csv
import io
import json
import math
import statistics
import sys
from collections.abc import Mapping
from typing import Any

MAX_REQUEST_BYTES = 1_000_000
MAX_CSV_CHARS = 512_000
MAX_ROWS = 20_000
MAX_COLUMNS = 64
_ALLOWED_FIELDS = {"schema_version", "request_id", "session_id", "module", "action", "inputs", "workspace_root", "timeout_seconds", "approval_token"}


def _result(request_id: str, status: str, data: dict[str, Any] | None = None, error: str | None = None) -> dict[str, Any]:
    return {"schema_version": "1.0", "request_id": request_id, "status": status, "data": data or {}, "error": error, "duration_ms": 0}


def _analyze(csv_text: str) -> dict[str, Any]:
    if not isinstance(csv_text, str) or not csv_text.strip() or len(csv_text) > MAX_CSV_CHARS:
        raise ValueError("CSV text must be non-empty and within the size limit")
    try:
        rows = list(csv.reader(io.StringIO(csv_text, newline=""), strict=True))
    except csv.Error as exc:
        raise ValueError("CSV format is invalid") from exc
    if not rows or len(rows) > MAX_ROWS + 1:
        raise ValueError("CSV row count is outside the supported range")
    headers = rows[0]
    if not 1 <= len(headers) <= MAX_COLUMNS:
        raise ValueError("CSV column count is outside the supported range")
    normalized: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(headers, 1):
        name = (value.strip() or f"column_{index}")[:120]
        candidate = name
        suffix = 2
        while candidate in seen:
            candidate = f"{name[:110]}_{suffix}"
            suffix += 1
        seen.add(candidate)
        normalized.append(candidate)
    data_rows = rows[1:]
    if any(len(row) != len(headers) for row in data_rows):
        raise ValueError("CSV rows must have the same number of columns as the header")
    missing = {name: 0 for name in normalized}
    numeric: dict[str, list[float]] = {name: [] for name in normalized}
    for row in data_rows:
        for index, value in enumerate(row):
            value = value.strip()
            name = normalized[index]
            if not value:
                missing[name] += 1
                continue
            try:
                number = float(value)
            except ValueError:
                continue
            if math.isfinite(number):
                numeric[name].append(number)
    summary: dict[str, dict[str, float | int]] = {}
    for name, values in numeric.items():
        if values:
            summary[name] = {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "mean": statistics.fmean(values),
                "median": statistics.median(values),
            }
    return {
        "rows": len(data_rows),
        "columns": normalized,
        "missing_values": missing,
        "numeric_summary": summary,
        "sample_rows": [dict(zip(normalized, row)) for row in data_rows[:5]],
        "read_only": True,
    }


def handle_request(request: Any) -> dict[str, Any]:
    if not isinstance(request, Mapping) or set(request) - _ALLOWED_FIELDS:
        return _result("unknown", "invalid_request", error="request shape is invalid")
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 128:
        return _result("unknown", "invalid_request", error="request_id is invalid")
    if request.get("schema_version") != "1.0" or request.get("module") != "data":
        return _result(request_id, "invalid_request", error="module or schema version is invalid")
    action, inputs = request.get("action"), request.get("inputs", {})
    if action == "health":
        return _result(request_id, "success", {"healthy": True})
    if action != "analyze" or not isinstance(inputs, Mapping):
        return _result(request_id, "permission_denied", error="unsupported TARA-Data capability")
    try:
        data = _analyze(inputs.get("csv_text"))
    except ValueError as exc:
        return _result(request_id, "invalid_request", error=str(exc))
    return _result(request_id, "success", data)


def main() -> int:
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        result = _result("unknown", "invalid_request", error="request exceeds the size limit")
    else:
        try:
            request = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            result = _result("unknown", "invalid_request", error="request must be UTF-8 JSON")
        else:
            result = handle_request(request)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
