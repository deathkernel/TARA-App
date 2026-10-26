"""Local deterministic intent router; no external model or API is required."""
from __future__ import annotations

import re
from typing import Any, Mapping

from tara_app.contracts import RouteDecision, SCHEMA_VERSION

_TOKEN = re.compile(r"[a-z0-9+#.-]+")
_SIDE_EFFECT = re.compile(
    r"\b(?:create|open|file)\s+(?:a\s+)?(?:github\s+)?issue\b|"
    r"\b(?:send|publish|delete|remove|install|commit|merge|execute|run)\b",
    re.IGNORECASE,
)
_CODE = re.compile(r"\b(?:code|coding|debug|bug|compile|refactor|function|class|script|program|repository|repo|pull request|test failure)\b", re.I)
_RESEARCH = re.compile(r"\b(?:research|sources?|citations?|latest|current|recent|today|news|paper|studies|evidence|look up|search the web)\b", re.I)
_PLANNER = re.compile(r"\b(?:plan|break down|roadmap|steps|schedule|milestones|prioritize)\b", re.I)
_CREATIVE = re.compile(r"\b(?:poem|story|lyrics|brainstorm|creative|rewrite|draft|write a|compose)\b", re.I)
_MEMORY_STORE = re.compile(r"\b(?:remember|save to memory|store this)\b", re.I)
_MEMORY_FORGET = re.compile(r"\b(?:forget|delete from memory|remove memory)\b", re.I)
_MEMORY_SEARCH = re.compile(r"\b(?:what do you remember|search memory|my saved memory)\b", re.I)


class BuiltinRouter:
    """Select the best available specialist from request intent and attachments."""

    def route(self, request: Mapping[str, Any]) -> RouteDecision:
        request_id = request.get("request_id") if isinstance(request, Mapping) else None
        if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 128:
            return RouteDecision("unknown", "invalid_request", None, None, "invalid_request", "Request ID is invalid")
        question = request.get("question")
        capabilities = request.get("available_capabilities", [])
        attachments = request.get("attachments", [])
        if not isinstance(question, str) or not question.strip() or len(question) > 20_000:
            return RouteDecision(request_id, "invalid_request", None, None, "invalid_request", "Question is invalid")
        if not isinstance(capabilities, list) or any(not isinstance(item, str) for item in capabilities):
            return RouteDecision(request_id, "invalid_request", None, None, "invalid_request", "Capability list is invalid")
        if not isinstance(attachments, list) or any(not isinstance(item, Mapping) for item in attachments):
            return RouteDecision(request_id, "invalid_request", None, None, "invalid_request", "Attachment list is invalid")

        available = set(capabilities)
        normalized = question.casefold()
        target: tuple[str, str, str, str] | None = None
        if _SIDE_EFFECT.search(question):
            if "security.assess" in available:
                return RouteDecision(
                    request_id, "routed", "security", "assess", "approval_gate",
                    "This request could change external or local state and needs a security review.",
                    intended_module="action", intended_action="execute", requires_approval=True,
                    policy_tags=("side_effect", "human_approval"),
                )
            return RouteDecision(
                request_id, "unavailable", None, None, "side_effects_disabled",
                "TARA requires the Security and approval workflow before it can perform changes.",
                intended_module="action", intended_action="execute", policy_tags=("side_effect",),
            )

        media = [str(item.get("media_type", "")).casefold() for item in attachments]
        if any(kind.startswith("image/") for kind in media):
            target = ("vision", "analyze", "image_attachment", "An image was attached.")
        elif any(kind.startswith("audio/") for kind in media):
            target = ("voice", "transcribe", "audio_attachment", "Audio was attached.")
        elif any(kind in {"text/csv", "application/csv"} for kind in media):
            target = ("data", "analyze", "csv_attachment", "A CSV file was attached.")
        elif any(kind.startswith("text/") or kind in {"application/octet-stream", "application/json"} for kind in media):
            target = ("code", "plan", "source_attachment", "Source files were attached.")

        if target is None:
            if _MEMORY_STORE.search(normalized):
                target = ("memory", "store", "memory_write", "The user requested explicit memory storage.")
            elif _MEMORY_FORGET.search(normalized):
                target = ("memory", "forget", "memory_write", "The user requested explicit memory deletion.")
            elif _MEMORY_SEARCH.search(normalized):
                target = ("memory", "search", "memory_lookup", "The user asked about saved memory.")
            elif _RESEARCH.search(normalized):
                target = ("research", "answer", "research_intent", "The request asks for current or sourced information.")
            elif _PLANNER.search(normalized):
                target = ("planner", "plan", "planning_intent", "The request asks for a structured plan.")
            elif _CREATIVE.search(normalized):
                target = ("creative", "write", "creative_intent", "The request asks for creative writing.")
            elif _CODE.search(normalized):
                target = ("code", "plan", "coding_intent", "The request is a coding task.")
            else:
                target = ("chat", "respond", "conversation", "General conversation.")

        module, action, code, reason = target
        capability_id = f"{module}.{action}"
        if capability_id not in available:
            return RouteDecision(
                request_id, "unavailable", None, None, "capability_unavailable",
                f"The {module} specialist is not installed or enabled.",
                intended_module=module, intended_action=action,
            )
        return RouteDecision(
            request_id, "routed", module, action, code, reason,
            schema_version=SCHEMA_VERSION,
        )
