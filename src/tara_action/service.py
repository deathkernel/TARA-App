"""Explicitly approved, allowlisted local desktop and GitHub actions."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import webbrowser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit

MODULE_ID = "action"
CAPABILITIES = ("execute",)
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
_MAX_RESPONSE_BYTES = 64_000
_APP_COMMANDS: dict[str, dict[str, tuple[str, ...] | None]] = {
    "calculator": {"windows": ("calc.exe",), "darwin": ("open", "-a", "Calculator"), "linux": ("gnome-calculator",)},
    "notepad": {"windows": ("notepad.exe",), "darwin": ("open", "-a", "TextEdit"), "linux": ("gedit",)},
    "paint": {"windows": ("mspaint.exe",), "darwin": None, "linux": ("pinta",)},
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _allowed_repositories() -> frozenset[str]:
    values = os.environ.get("TARA_ACTION_GITHUB_REPOSITORIES", "")
    return frozenset(item.strip().lower() for item in values.split(",") if _REPOSITORY.fullmatch(item.strip()))


def health() -> bool:
    """The local action adapter is ready; remote GitHub writes are checked per operation."""
    return True


def _platform_name() -> str | None:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "darwin"
    if sys.platform.startswith("linux"):
        return "linux"
    return None


def _open_application(application: Any) -> tuple[str, dict[str, Any], str | None]:
    if not isinstance(application, str) or application not in _APP_COMMANDS:
        return "permission_denied", {}, "application is not in the local allowlist"
    platform = _platform_name()
    command = _APP_COMMANDS[application].get(platform) if platform else None
    if not command:
        return "unavailable", {}, "this application is not configured for the current operating system"
    executable = shutil.which(command[0])
    if not executable:
        return "unavailable", {}, "the allowlisted application is not installed or available on PATH"
    try:
        if platform == "darwin":
            # The executable and app name come only from the fixed allowlist.
            # Waiting for 'open -a' lets us report a missing/unlaunchable app.
            completed = subprocess.run(
                ["/usr/bin/open", *command[1:]],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                check=False,
                timeout=10,
            )
            if completed.returncode != 0:
                return "unavailable", {}, "the allowlisted application is not installed or could not be launched"
        elif platform == "windows":
            # Windows shell association is not used; start only the fixed app name.
            os.startfile(command[0])  # type: ignore[attr-defined]
        else:
            # Linux executable is resolved from a fixed per-app allowlist; no shell.
            # spawnv does not invoke a shell; executable and argv are
            # derived exclusively from the fixed _APP_COMMANDS allowlist.
            os.spawnv(os.P_NOWAIT, executable, [executable, *command[1:]])
    except (OSError, ValueError, subprocess.SubprocessError):
        return "unavailable", {}, "the allowlisted application could not be opened"
    return "success", {"operation": "desktop.app.open", "application": application}, None


def _open_website(value: Any) -> tuple[str, dict[str, Any], str | None]:
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        return "invalid_request", {}, "website address must contain 1 to 2048 characters"
    url = value.strip()
    if any(ord(char) < 32 or ord(char) == 127 for char in url):
        return "invalid_request", {}, "website address contains invalid characters"
    if url.casefold().startswith("www."):
        url = "https://" + url
    elif "://" not in url:
        url = "https://" + url
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        return "invalid_request", {}, "website address is invalid"
    if (
        parsed.scheme.casefold() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or (port is not None and not 1 <= port <= 65535)
    ):
        return "invalid_request", {}, "only valid HTTP or HTTPS websites can be opened"
    try:
        opened = webbrowser.open(url, new=2, autoraise=True)
    except Exception:
        opened = False
    if not opened:
        return "unavailable", {}, "no available browser could open the website"
    return "success", {"operation": "desktop.url.open", "url": url}, None


def execute(action: str, inputs: dict[str, Any], *, approval_token: str | None = None) -> tuple[str, dict[str, Any], str | None]:
    if not isinstance(inputs, dict):
        return "invalid_request", {}, "action inputs must be an object"
    if action != "execute":
        return "permission_denied", {}, "unsupported action capability"
    if not isinstance(approval_token, str) or not approval_token.strip():
        return "approval_required", {}, "an explicit one-time approval token is required"
    # These fields are orchestration metadata, not action arguments. Ignore them
    # here, then continue to reject every unknown operation-specific input.
    inputs = {key: value for key, value in inputs.items()
              if key not in {"question", "attachments", "policy_tags"}}
    operation = inputs.get("operation")
    if operation == "desktop.app.open":
        if set(inputs) - {"operation", "application"}:
            return "invalid_request", {}, "application request contains unsupported fields"
        return _open_application(inputs.get("application"))
    if operation == "desktop.url.open":
        if set(inputs) - {"operation", "url"}:
            return "invalid_request", {}, "website request contains unsupported fields"
        return _open_website(inputs.get("url"))
    if operation != "github.issue.create":
        return "permission_denied", {}, "only allowlisted local desktop, browser, and GitHub issue actions are supported"
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

