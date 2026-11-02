"""OmniRoute-only model catalogue and inference adapter."""
from __future__ import annotations

import json
import os
import re
import sys
import time
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

MAX_REQUEST = 64_000
MAX_RESPONSE = 1_000_000
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, msg, headers, new_url):
        return None


def _omniroute_config() -> tuple[str, str, str]:
    base = os.environ.get("TARA_MODELS_API_BASE_URL", os.environ.get("TARA_OMNIROUTE_BASE_URL", "http://127.0.0.1:20128/v1")).strip().rstrip("/")
    try:
        parsed = urlsplit(base)
        port = parsed.port
    except ValueError:
        raise ValueError("OmniRoute endpoint is invalid") from None
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.username or parsed.password
        or parsed.path != "/v1"
        or parsed.query or parsed.fragment
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise ValueError("TARA Model Hub only accepts the local OmniRoute /v1 endpoint")
    key = os.environ.get("TARA_MODELS_API_KEY", os.environ.get("TARA_OMNIROUTE_API_KEY", "")).strip()
    if not key or len(key) > 4096 or any(ord(char) < 33 or ord(char) == 127 for char in key):
        raise ValueError("OmniRoute API key is missing or invalid")
    default_model = os.environ.get("TARA_MODELS_MODEL", "auto").strip()
    if not _MODEL_RE.fullmatch(default_model):
        raise ValueError("configured OmniRoute model route is invalid")
    return base, key, default_model


def _http_json(url: str, *, api_key: str, method: str = "GET", body: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    raw_body = json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8") if body is not None else None
    request = Request(
        url,
        data=raw_body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "TARA-App/0.1",
        },
        method=method,
    )
    try:
        with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE + 1)
    except HTTPError as exc:
        raise ValueError(f"OmniRoute returned HTTP {exc.code}") from None
    except (URLError, TimeoutError, OSError):
        raise ValueError("OmniRoute gateway is unreachable") from None
    if len(raw) > MAX_RESPONSE:
        raise ValueError("OmniRoute response exceeded the size limit")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("OmniRoute returned invalid JSON") from None
    if not isinstance(data, dict):
        raise ValueError("OmniRoute returned an unexpected response")
    return data


def _catalog(base: str, key: str) -> list[dict[str, Any]]:
    data = _http_json(base + "/models", api_key=key)
    entries = data.get("data", [])
    if not isinstance(entries, list):
        raise ValueError("OmniRoute returned an invalid model catalogue")
    models = []
    for item in entries:
        if not isinstance(item, Mapping) or not isinstance(item.get("id"), str):
            continue
        model_id = item["id"]
        models.append({
            "id": model_id,
            "provider": "omniroute",
            "label": model_id,
            "owned_by": item.get("owned_by"),
            "availability": "Depends on the providers and credentials configured in OmniRoute.",
        })
    return models


def _generate(base: str, key: str, model: str, question: str) -> tuple[str, str]:
    data = _http_json(
        base + "/chat/completions",
        api_key=key,
        method="POST",
        timeout=120,
        body={
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": "You are TARA, a helpful assistant. Answer clearly and directly. State uncertainty and never invent sources."},
                {"role": "user", "content": question},
            ],
            "max_tokens": 4096,
            "temperature": 0.4,
        },
    )
    choices = data.get("choices")
    first = choices[0] if isinstance(choices, list) and choices else None
    message = first.get("message") if isinstance(first, Mapping) else None
    answer = message.get("content") if isinstance(message, Mapping) else None
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("OmniRoute returned an empty answer")
    response_model = data.get("model") if isinstance(data.get("model"), str) else model
    return answer.strip(), response_model


def handle_request(request: Any) -> dict[str, Any]:
    started = time.monotonic()

    def result(request_id: str, status: str, data: dict[str, Any] | None = None, error: str | None = None):
        return {
            "schema_version": "1.0",
            "request_id": request_id,
            "status": status,
            "data": data or {},
            "error": error,
            "duration_ms": max(0, int((time.monotonic() - started) * 1000)),
        }

    allowed = {"schema_version", "request_id", "session_id", "module", "action", "inputs", "workspace_root", "timeout_seconds", "approval_token"}
    if not isinstance(request, dict) or set(request) - allowed:
        return result("unknown", "invalid_request", error="request shape is invalid")
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 128:
        return result("unknown", "invalid_request", error="request_id is invalid")
    if request.get("schema_version") != "1.0" or request.get("module") != "models":
        return result(request_id, "invalid_request", error="module or schema version is invalid")
    inputs = request.get("inputs", {})
    if not isinstance(inputs, dict):
        return result(request_id, "invalid_request", error="model inputs are invalid")
    action = request.get("action")
    if action not in {"health", "catalog", "generate"}:
        return result(request_id, "permission_denied", error="unsupported model capability")
    try:
        base, key, default_model = _omniroute_config()
        if action == "health":
            return result(request_id, "success", {"healthy": True, "provider": "omniroute", "gateway_configured": True})
        if action == "catalog":
            models = _catalog(base, key)
            route = {"id": default_model, "provider": "omniroute", "label": f"Default route ({default_model})", "availability": "Resolved by OmniRoute at request time."}
            if not any(item["id"] == default_model for item in models):
                models.insert(0, route)
            lines = ["# OmniRoute Model Hub", "All model requests are routed through your configured OmniRoute gateway.", ""]
            lines.extend(f"- {item['id']} — {item.get('owned_by') or 'provider selected by OmniRoute'}" for item in models)
            lines.extend(["", "Provider availability, quotas, and billing depend on your OmniRoute configuration."])
            return result(request_id, "success", {
                "text": "\n".join(lines),
                "models": models,
                "provider": "omniroute",
                "remote_data_transfer": False,
            })
        question = inputs.get("question")
        if not isinstance(question, str) or not question.strip() or len(question) > 20_000:
            return result(request_id, "invalid_request", error="question is invalid")
        model = inputs.get("model")
        if model is None:
            selection = re.match(
                r"^\s*(?:please\s+)?(?:use|switch to|try|ask|run with)\s+(?:model\s+)?"
                r"(?P<model>[A-Za-z0-9][A-Za-z0-9._:/-]{0,199})\s*[:,-]?\s*",
                question,
                re.I,
            )
            if selection and _MODEL_RE.fullmatch(selection.group("model")):
                model = selection.group("model")
                question = question[selection.end():].strip() or question
            else:
                model = default_model
        if not isinstance(model, str) or not _MODEL_RE.fullmatch(model):
            return result(request_id, "invalid_request", error="model route is invalid")
        answer, response_model = _generate(base, key, model, question.strip())
        return result(request_id, "success", {
            "text": answer,
            "provider": "omniroute",
            "model": response_model,
            "remote_data_transfer": True,
        })
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        return result(request_id, "unavailable", error=str(exc)[:500] or "OmniRoute is unavailable")


def main() -> int:
    raw = sys.stdin.buffer.read(MAX_REQUEST + 1)
    if len(raw) > MAX_REQUEST:
        response = {
            "schema_version": "1.0", "request_id": "unknown", "status": "invalid_request",
            "data": {}, "error": "request exceeds the size limit", "duration_ms": 0,
        }
    else:
        try:
            request = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            response = {
                "schema_version": "1.0", "request_id": "unknown", "status": "invalid_request",
                "data": {}, "error": "request must be UTF-8 JSON", "duration_ms": 0,
            }
        else:
            response = handle_request(request)
    sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
