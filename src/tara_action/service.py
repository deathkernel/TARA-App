"""Allowlisted GitHub issue creation for explicitly approved TARA actions."""

from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote

MODULE_ID = "action"
CAPABILITIES = ("execute",)
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
_MAX_RESPONSE_BYTES = 64_000


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _allowed_repositories() -> frozenset[str]:
    values = os.environ.get("TARA_ACTION_GITHUB_REPOSITORIES", "")
    return frozenset(item.strip().lower() for item in values.split(",") if _REPOSITORY.fullmatch(item.strip()))


def health() -> bool:
    """Report ready only when a token and at least one repo allowlist entry exist."""
    return bool(os.environ.get("GITHUB_TOKEN", "").strip() and _allowed_repositories())


def execute(action: str, inputs: dict[str, Any], *, approval_token: str | None = None) -> tuple[str, dict[str, Any], str | None]:
    if action != "execute":
        return "permission_denied", {}, "unsupported action capability"
    if not isinstance(approval_token, str) or not approval_token.strip():
        return "approval_required", {}, "an explicit one-time approval token is required"
    operation = inputs.get("operation")
    if operation != "github.issue.create":
        return "permission_denied", {}, "only allowlisted GitHub issue creation is supported"
    repository = inputs.get("repository")
    title = inputs.get("title")
    body = inputs.get("body", "")
    if not isinstance(repository, str) or not _REPOSITORY.fullmatch(repository):
        return "invalid_request", {}, "repository must use owner/name form"
    if repository.lower() not in _allowed_repositories():
        return "permission_denied", {}, "repository is not in TARA_ACTION_GITHUB_REPOSITORIES"
    if not isinstance(title, str) or not title.strip() or len(title) > 256 or any(ord(char) < 32 and char not in "\t" for char in title):
        return "invalid_request", {}, "issue title must contain 1 to 256 printable characters"
    if not isinstance(body, str) or len(body) > 10_000:
        return "invalid_request", {}, "issue body must be at most 10000 characters"
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        return "unavailable", {}, "GitHub credentials are not configured"

    owner, name = repository.split("/", 1)
    url = f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(name, safe='')}/issues"
    payload = json.dumps({"title": title.strip(), "body": body}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "TARA-Action/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=15) as response:
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
        if len(raw) > _MAX_RESPONSE_BYTES:
            return "failed", {}, "GitHub returned an oversized response"
        result = json.loads(raw.decode("utf-8"))
    except HTTPError as exc:
        if exc.code in {401, 403}:
            return "permission_denied", {}, "GitHub rejected the configured credentials or repository permission"
        if exc.code == 422:
            return "invalid_request", {}, "GitHub rejected the issue details"
        return "unavailable", {}, "GitHub issue creation is unavailable"
    except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return "unavailable", {}, "GitHub issue creation is unavailable"
    if not isinstance(result, dict) or not isinstance(result.get("number"), int) or not isinstance(result.get("html_url"), str):
        return "failed", {}, "GitHub returned an invalid issue result"
    return "success", {
        "operation": operation,
        "repository": repository,
        "issue_number": result["number"],
        "url": result["html_url"],
        "title": title.strip(),
    }, None

