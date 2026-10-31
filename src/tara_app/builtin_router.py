"""Local deterministic intent router; no external model or API is required."""
from __future__ import annotations

import re
from typing import Any, Mapping
from urllib.parse import urlsplit

from tara_app.contracts import RouteDecision, SCHEMA_VERSION

_TOKEN = re.compile(r"[a-z0-9+#.-]+")
_SIDE_EFFECT = re.compile(
    r"\b(?:create|open|file)\s+(?:a\s+)?(?:github\s+)?issue\b|"
    r"\b(?:send|publish|delete|remove|install|commit|merge|execute|run)\b",
    re.IGNORECASE,
)
_REPOSITORY_AUDIT_ONLY = re.compile(r"^\s*(?:(?:please\s+)?(?:run|perform|do)\s+(?:a\s+)?(?:repository|repo|project)\s+audit|(?:please\s+)?(?:audit|inspect|check)\s+(?:(?:the|this|my|our)\s+)?(?:repository|repo|project))\s*[.!?]*$", re.I)
_REPOSITORY_AUDIT = re.compile(r"\b(?:audit|inspect|check)\s+(?:(?:the|this|my|our)\s+)?(?:repository|repo|project)\b|\b(?:repository|repo|project)\s+(?:audit|health check)\b", re.I)
_CODE = re.compile(r"\b(?:code|coding|debug|bug|compile|refactor|function|class|script|program|repository|repo|pull request|test failure)\b", re.I)
_RESEARCH = re.compile(r"\b(?:research|sources?|citations?|latest|current|recent|today|news|paper|studies|evidence|look up|search the web)\b", re.I)
_PLANNER = re.compile(r"\b(?:plan|break down|roadmap|steps|schedule|milestones|prioritize)\b", re.I)
_STUDY = re.compile(r"\b(?:study mode|make (?:me )?(?:notes|a quiz|flashcards?)|create (?:notes|a quiz|flashcards?)|generate (?:notes|a quiz|flashcards?)|(?:mcq|flashcards?) from|study plan|revision plan|quiz me on|summari[sz]e (?:this|these|the chapter|the notes))\b", re.I)
_WEATHER = re.compile(r"\b(?:weather|forecast|temperature|rain(?:\s+chance)?|humidity|wind speed)\b", re.I)
_MODELS_CATALOG = re.compile(r"\b(?:list|show|discover|available|catalogue|catalog)\b.{0,35}\b(?:models?|gemini|gpt-oss|openai)\b|\b(?:models?|gemini|gpt-oss)\b.{0,35}\b(?:free|available|catalogue|catalog)\b", re.I)
_MODELS_USE = re.compile(r"\b(?:use|switch to|try|ask|run with)\s+(?:(?:the|openai)\s+)?(?P<model>gemini(?:-[a-z0-9.-]+)?|gpt-oss(?::[a-z0-9.-]+)?)\b", re.I)
_CREATIVE = re.compile(r"\b(?:poem|story|lyrics|brainstorm|creative|rewrite|draft|write a|compose)\b", re.I)
_MEMORY_STORE = re.compile(r"\b(?:remember|save to memory|store this)\b", re.I)
_MEMORY_FORGET = re.compile(r"\b(?:forget|delete from memory|remove memory)\b", re.I)
_MEMORY_SEARCH = re.compile(r"\b(?:what do you remember|search memory|my saved memory)\b", re.I)
_VOICE_SPEAK = re.compile(r"\b(?:read|speak|say)(?:\s+(?:this|that|it))?(?:\s+(?:aloud|out\s+loud|to\s+me))\b", re.I)
_DESKTOP_APP_OPEN = re.compile(
    r"\s*(?:(?:please\s+)?(?:open|launch|start)\s+(?:the\s+)?(?:calculator|calc|notepad|text editor|paint|mspaint)|"
    r"(?:calculator|calc|notepad|paint)\s+(?:kholo|khol(?:o)?|open\s+karo|start\s+karo))\s*[.!]?\s*",
    re.I,
)
_WEBSITE_OPEN = re.compile(
    r"""\s*(?:please\s+)?(?:open|visit|go\s+to|browse|kholo|khol(?:o)?)\s+(?:the\s+)?"""
    r"""(?P<url>https?://[^\s<>\"']+|www\.[^\s<>\"']+|[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}\.)+[A-Za-z]{2,63}(?::\d{1,5})?(?:[/?#][^\s<>\"']*)?)\s*[.!?]?\s*""",
    re.I,
)
 
def _valid_website_open(question: str) -> bool:
    """Validate website requests before they can enter the approval flow."""
    match = _WEBSITE_OPEN.fullmatch(question.strip())
    if match is None:
        return False
    raw_url = match.group("url")
    if not raw_url.casefold().startswith(("http://", "https://")):
        raw_url = raw_url.rstrip(".,!?;:")
        raw_url = "https://" + raw_url
    if len(raw_url) > 2048 or any(ord(char) < 32 or ord(char) == 127 for char in raw_url):
        return False
    try:
        parsed = urlsplit(raw_url)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme.casefold() in {"http", "https"}
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and (port is None or 1 <= port <= 65535)
    )



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
        memory_write_action = (
            "forget" if _MEMORY_FORGET.search(normalized)
            else "store" if _MEMORY_STORE.search(normalized) and not _MEMORY_SEARCH.search(normalized)
            else None
        )
        if memory_write_action is not None:
            if "security.assess" not in available:
                return RouteDecision(
                    request_id, "unavailable", None, None, "security_unavailable",
                    "Local memory changes need TARA-Security and your explicit approval.",
                    intended_module="memory", intended_action=memory_write_action,
                    policy_tags=("memory_write", "consent_required"),
                )
            return RouteDecision(
                request_id, "routed", "security", "assess", "memory_write_approval",
                "A local memory change needs your explicit approval.",
                intended_module="memory", intended_action=memory_write_action,
                requires_approval=True,
                policy_tags=("memory_write", "consent_required", "human_approval"),
            )
        website_match = _WEBSITE_OPEN.fullmatch(question.strip())
        if website_match is not None and not _valid_website_open(question):
            return RouteDecision(
                request_id, "invalid_request", None, None, "invalid_website_url",
                "The website address is invalid or exceeds the 2048-character limit.",
            )
        if _DESKTOP_APP_OPEN.fullmatch(question.strip()) or website_match is not None:
            if "security.assess" not in available or "action.execute" not in available:
                return RouteDecision(
                    request_id, "unavailable", None, None, "desktop_automation_unavailable",
                    "TARA's approved desktop automation is not installed or enabled.",
                    intended_module="action", intended_action="execute",
                    policy_tags=("desktop_automation",),
                )
            return RouteDecision(
                request_id, "routed", "security", "assess", "desktop_automation_approval",
                "This local automation needs your approval before it runs.",
                intended_module="action", intended_action="execute", requires_approval=True,
                policy_tags=("desktop_automation", "human_approval"),
            )
        if _SIDE_EFFECT.search(question) and not _REPOSITORY_AUDIT_ONLY.fullmatch(question.strip()):
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

        if _REPOSITORY_AUDIT.search(normalized):
            target = ("chat", "audit_repository", "repository_audit", "The user explicitly requested a read-only audit of the configured local repository.")

        media = [str(item.get("media_type", "")).casefold() for item in attachments]
        if any(kind.startswith("image/") for kind in media):
            target = ("vision", "analyze", "image_attachment", "An image was attached.")
        elif any(kind.startswith("audio/") for kind in media):
            target = ("voice", "transcribe", "audio_attachment", "Audio was attached.")
        elif any(kind in {"text/csv", "application/csv"} for kind in media):
            target = ("data", "analyze", "csv_attachment", "A CSV file was attached.")
        elif any(kind.startswith("text/") or kind in {"application/octet-stream", "application/json"} for kind in media):
            target = ("code", "plan", "source_attachment", "Source files were attached.")

        # Explicit study intent must take precedence over the generic text-attachment
        # route so uploaded notes are passed to TARA-Study rather than TARA-Code.
        if _STUDY.search(normalized):
            target = ("study", "create", "study_intent", "The request asks for study notes, a quiz, flashcards, or a revision plan.")

        if target is None:
            if _MEMORY_STORE.search(normalized):
                target = ("memory", "store", "memory_write", "The user requested explicit memory storage.")
            elif _MEMORY_FORGET.search(normalized):
                target = ("memory", "forget", "memory_write", "The user requested explicit memory deletion.")
            elif _MEMORY_SEARCH.search(normalized):
                target = ("memory", "search", "memory_lookup", "The user asked about saved memory.")
            elif _VOICE_SPEAK.search(normalized):
                target = ("voice", "speak", "read_aloud", "The user asked for local read-aloud.")
            elif _MODELS_CATALOG.search(normalized):
                target = ("models", "catalog", "model_catalog", "The user asks to discover available free-first models.")
            elif _MODELS_USE.search(normalized):
                target = ("models", "generate", "model_selection", "The user explicitly selected a model provider.")
            elif _WEATHER.search(normalized):
                target = ("weather", "forecast", "weather_lookup", "The user asks for current weather or a forecast.")
            elif _STUDY.search(normalized):
                target = ("study", "create", "study_intent", "The request asks for study notes, a quiz, flashcards, or a revision plan.")
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
