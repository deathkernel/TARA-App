"""Bounded research adapter using free public Crossref and Wikipedia APIs."""
from __future__ import annotations

import json
import sys
import time
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, ProxyHandler

MAX_REQUEST_BYTES = 64_000
MAX_RESPONSE_BYTES = 512_000
_ALLOWED_FIELDS = {"schema_version", "request_id", "session_id", "module", "action", "inputs", "workspace_root", "timeout_seconds", "approval_token"}


def _result(request_id: str, status: str, data: dict[str, Any] | None = None, error: str | None = None, duration_ms: int = 0) -> dict[str, Any]:
    return {"schema_version": "1.0", "request_id": request_id, "status": status, "data": data or {}, "error": error, "duration_ms": duration_ms}


def _get_json(host: str, path: str, query: dict[str, str]) -> Any:
    url = "https://" + host + path + "?" + urlencode(query)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "TARA-App/0.1 (https://github.com/deathkernel/TARA-App)"})
    with build_opener(ProxyHandler({})).open(request, timeout=10) as response:
        if response.geturl().split("/", 3)[:3] != ["https:", "", host]:
            raise ValueError("public research endpoint redirected unexpectedly")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("public research response exceeded the size limit")
    return json.loads(raw.decode("utf-8"))


def _crossref(query: str) -> list[dict[str, str]]:
    payload = _get_json("api.crossref.org", "/works", {"query.bibliographic": query, "rows": "4"})
    message = payload.get("message", {}) if isinstance(payload, Mapping) else {}
    items = message.get("items", []) if isinstance(message, Mapping) else []
    output = []
    for item in items[:4] if isinstance(items, list) else []:
        if not isinstance(item, Mapping):
            continue
        titles = item.get("title", [])
        title = titles[0] if isinstance(titles, list) and titles else ""
        doi = item.get("DOI")
        if not isinstance(title, str) or not title.strip():
            continue
        entry = {"title": title[:300], "source": "Crossref"}
        if isinstance(doi, str) and doi.startswith("10.") and len(doi) <= 200:
            entry["url"] = "https://doi.org/" + doi
        authors = item.get("author", [])
        if isinstance(authors, list) and authors and isinstance(authors[0], Mapping):
            family = authors[0].get("family")
            if isinstance(family, str):
                entry["author"] = family[:100]
        date_parts = item.get("published-print", item.get("published-online", {}))
        if isinstance(date_parts, Mapping):
            parts = date_parts.get("date-parts", [])
            if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
                entry["year"] = str(parts[0][0])[:4]
        output.append(entry)
    return output


def _wikipedia(query: str) -> list[dict[str, str]]:
    payload = _get_json(
        "en.wikipedia.org", "/w/api.php",
        {"action": "query", "list": "search", "srsearch": query, "format": "json", "utf8": "1", "srlimit": "4"},
    )
    query_payload = payload.get("query", {}) if isinstance(payload, Mapping) else {}
    search = query_payload.get("search", []) if isinstance(query_payload, Mapping) else []
    output = []
    for item in search[:4] if isinstance(search, list) else []:
        if not isinstance(item, Mapping):
            continue
        title, snippet = item.get("title"), item.get("snippet")
        if not isinstance(title, str) or not title.strip():
            continue
        entry = {"title": title[:300], "source": "Wikipedia"}
        if isinstance(snippet, str):
            entry["snippet"] = " ".join(snippet.replace("<span class=\"searchmatch\">", "").replace("</span>", "").split())[:600]
        entry["url"] = "https://en.wikipedia.org/wiki/" + title.replace(" ", "_")
        output.append(entry)
    return output


def handle_request(request: Any) -> dict[str, Any]:
    if not isinstance(request, Mapping) or set(request) - _ALLOWED_FIELDS:
        return _result("unknown", "invalid_request", error="request shape is invalid")
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 128:
        return _result("unknown", "invalid_request", error="request_id is invalid")
    if request.get("schema_version") != "1.0" or request.get("module") != "research":
        return _result(request_id, "invalid_request", error="module or schema version is invalid")
    action, inputs = request.get("action"), request.get("inputs", {})
    if action == "health":
        return _result(request_id, "success", {"healthy": True, "providers": ["Crossref", "Wikipedia"]})
    if action != "answer" or not isinstance(inputs, Mapping):
        return _result(request_id, "permission_denied", error="unsupported TARA-Research capability")
    question = inputs.get("question")
    if not isinstance(question, str) or not question.strip() or len(question) > 1000:
        return _result(request_id, "invalid_request", error="research query must be non-empty and at most 1000 characters")
    started = time.monotonic()
    sources: list[dict[str, str]] = []
    failures = 0
    for search in (_crossref, _wikipedia):
        try:
            sources.extend(search(question.strip()))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
            failures += 1
    if not sources:
        return _result(request_id, "unavailable", error="free public research sources are temporarily unavailable", duration_ms=int((time.monotonic() - started) * 1000))
    lines = ["Public-source results for: " + question.strip(), "These are source records, not model-generated conclusions."]
    for index, source in enumerate(sources[:8], 1):
        line = f"{index}. [{source['source']}] {source['title']}"
        if source.get("author"):
            line += " — " + source["author"]
        if source.get("year"):
            line += " (" + source["year"] + ")"
        if source.get("url"):
            line += "\n   " + source["url"]
        if source.get("snippet"):
            line += "\n   " + source["snippet"]
        lines.append(line)
    if failures:
        lines.append("Some public sources did not respond; the results above may be incomplete.")
    return _result(
        request_id, "success",
        {"text": "\n\n".join(lines), "sources": sources[:8], "providers": ["Crossref", "Wikipedia"], "paid_model_used": False},
        duration_ms=int((time.monotonic() - started) * 1000),
    )


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
