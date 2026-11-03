"""Deterministic policy assessment. This module never performs actions."""
from __future__ import annotations
import re
from typing import Any

MODULE_ID = "security"
CAPABILITIES = ("assess",)
_HARMFUL = re.compile(r"\b(steal credentials|exfiltrat\w*|credential theft|ransomware|deploy malware|bypass authorization)\b", re.I)

def execute(action: str, inputs: dict[str, Any], *, approval_token: str | None = None) -> tuple[str, dict[str, Any], str | None]:
    if action != "assess":
        return "permission_denied", {}, "unsupported security capability"
    question = inputs.get("question", "")
    if not isinstance(question, str) or len(question) > 20_000:
        raise ValueError("question must be bounded text")
    module, intended_action = inputs.get("intended_module"), inputs.get("intended_action")
    tags = inputs.get("policy_tags", [])
    if module is not None and not isinstance(module, str):
        raise ValueError("intended_module must be text")
    if intended_action is not None and not isinstance(intended_action, str):
        raise ValueError("intended_action must be text")
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise ValueError("policy_tags must be a list of strings")
    target = f"{module or ''}.{intended_action or ''}".lower()
    if _HARMFUL.search(question):
        verdict, reason = "deny", "request indicates credential theft, malware, or authorization bypass"
    elif any(tag in {"side_effect", "consent_required", "environment_change", "sandbox_required"} for tag in tags):
        verdict, reason = "approval_required", "side-effecting capability requires separate user approval"
    elif any(word in target for word in ("execute", "repair", "store", "forget", "write", "send", "delete", "deploy", "purchase", "commit", "push")):
        verdict, reason = "approval_required", "requested capability may change external or persistent state"
    else:
        verdict, reason = "allow", "read-only security assessment may proceed"
    return "success", {"decision": verdict, "intended_module": module, "intended_action": intended_action, "reason": reason, "approval_token_present": bool(approval_token)}, None

