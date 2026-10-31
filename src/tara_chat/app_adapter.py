"""TARA-App boundary for the independent TARA-Chat conversation engine."""
from __future__ import annotations
import json
import os
import sys
import time
from collections.abc import Mapping
from typing import Any
from .brain import TARABrain
from .llm_provider_factory import provider_from_env
from .memory import LongTermMemory

MODULE_ID = "chat"
CAPABILITIES = ("respond", "audit_repository")
MAX_REQUEST_BYTES = 1_000_000
_ALLOWED_REQUEST_FIELDS = {"schema_version", "request_id", "session_id", "module", "action", "inputs", "workspace_root", "timeout_seconds", "approval_token"}


def _result(request_id: str, status: str, data: dict[str, Any] | None = None, error: str | None = None, duration_ms: int = 0) -> dict[str, Any]:
    return {"schema_version": "1.0", "request_id": request_id, "status": status, "data": data or {}, "error": error, "duration_ms": duration_ms}


def handle_request(request: Any) -> dict[str, Any]:
    if not isinstance(request, Mapping) or set(request) - _ALLOWED_REQUEST_FIELDS:
        return _result("unknown", "invalid_request", error="request shape is invalid")
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 128:
        return _result("unknown", "invalid_request", error="request_id is invalid")
    if request.get("schema_version") != "1.0" or request.get("module") != MODULE_ID:
        return _result(request_id, "invalid_request", error="module or schema version is invalid")
    action, inputs = request.get("action"), request.get("inputs", {})
    if not isinstance(action, str) or not isinstance(inputs, Mapping):
        return _result(request_id, "invalid_request", error="action or inputs are invalid")
    if action == "health":
        return _result(request_id, "success", {"healthy": True})
    if action == "audit_repository":
        question = inputs.get("question")
        attachments = inputs.get("attachments", [])
        if not isinstance(question, str) or not question.strip() or len(question) > 20_000:
            return _result(request_id, "invalid_request", error="audit request question is invalid")
        if not isinstance(attachments, list) or attachments:
            return _result(request_id, "invalid_request", error="repository audit does not accept attachments")
        start = time.monotonic()
        try:
            from pathlib import Path
            from .repository_audit import RepositoryAuditor

            report = RepositoryAuditor(Path.cwd()).audit()
        except (OSError, RuntimeError, ValueError):
            return _result(
                request_id, "unavailable",
                error="repository audit could not inspect the configured local working directory",
                duration_ms=max(0, int((time.monotonic() - start) * 1000)),
            )
        errors = [issue for issue in report.issues if issue.severity == "error"]
        warnings = [issue for issue in report.issues if issue.severity == "warning"]
        status = "HEALTHY" if report.healthy else "ISSUES FOUND"
        lines = [
            f"Repository audit: {status}",
            f"Files scanned: {report.files_scanned} (Python: {report.python_files}, workflows: {report.workflow_files})",
            f"Errors: {len(errors)} | Warnings: {len(warnings)}",
            f"Fingerprint: {report.fingerprint}",
        ]
        for issue in report.issues[:20]:
            lines.append(f"- {issue.severity.upper()} {issue.code} {issue.path}: {issue.detail[:240]}")
        if len(report.issues) > 20:
            lines.append(f"... {len(report.issues) - 20} additional findings omitted.")
        return _result(
            request_id, "success",
            {
                "text": "\n".join(lines),
                "healthy": report.healthy,
                "files_scanned": report.files_scanned,
                "python_files": report.python_files,
                "workflow_files": report.workflow_files,
                "error_count": len(errors),
                "warning_count": len(warnings),
                "fingerprint": report.fingerprint,
                "issues": [
                    {"code": issue.code, "path": issue.path, "detail": issue.detail, "severity": issue.severity}
                    for issue in report.issues[:100]
                ],
                "remote_data_transfer": False,
            },
            duration_ms=max(0, int((time.monotonic() - start) * 1000)),
        )
    if action != "respond":
        return _result(request_id, "permission_denied", error="unsupported TARA-Chat capability")
    question = inputs.get("question")
    if not isinstance(question, str) or not question.strip() or len(question) > 20_000:
        return _result(request_id, "invalid_request", error="question must be non-empty bounded text")
    history = inputs.get("history", [])
    if not isinstance(history, list) or len(history) > 24:
        return _result(request_id, "invalid_request", error="history must contain at most 24 turns")
    normalized: list[tuple[str, str]] = []
    for item in history:
        if not isinstance(item, Mapping) or set(item) != {"role", "content"}:
            return _result(request_id, "invalid_request", error="history entries have an invalid shape")
        role, content = item.get("role"), item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str) or len(content) > 20_000:
            return _result(request_id, "invalid_request", error="history entry is invalid")
        normalized.append(("User" if role == "user" else "TARA", content))
    try:
        provider = provider_from_env()
    except (OSError, RuntimeError, ValueError):
        return _result(request_id, "unavailable", error="TARA-Chat provider configuration is unavailable")
    if provider is None:
        return _result(request_id, "unavailable", error="TARA-Chat has no language provider configured")
    memory_path = os.environ.get("TARA_CHAT_MEMORY_PATH", "").strip()
    brain = TARABrain(llm_provider=provider, memory=LongTermMemory(memory_path or None))
    brain.conversation_history = normalized
    start = time.monotonic()
    try:
        response = brain.respond(question.strip())
    except (OSError, RuntimeError, TypeError, ValueError):
        return _result(request_id, "unavailable", error="TARA-Chat could not produce a response", duration_ms=max(0, int((time.monotonic() - start) * 1000)))
    return _result(request_id, "success", {"text": response.text}, duration_ms=max(0, int((time.monotonic() - start) * 1000)))


def main() -> int:
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        sys.stdout.write(json.dumps(_result("unknown", "invalid_request", error="request exceeds the size limit")) + "\n")
        return 0
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
