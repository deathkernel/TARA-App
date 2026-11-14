"""Application boundary shared by every SITA interface.
 
The facade hides the coordinator, registry, adapters and integration details
from HTTP, desktop and CLI transports. It is intentionally thin in this first
migration slice; workflow persistence and durable application state follow in
later steps.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Mapping, Sequence

from tara_app.contracts import AdapterHealth, ModuleRequest


class ApplicationFacade:
    """Stable use-case boundary for local SITA interfaces."""

    def __init__(self, coordinator: Any) -> None:
        self._coordinator = coordinator

    @staticmethod
    def _adapter_health(adapter: Any) -> AdapterHealth:
        """Normalize one adapter's health result without leaking exceptions."""
        try:
            health = adapter.health()
        except Exception:
            return AdapterHealth("unavailable", "specialist health check failed")
        if not isinstance(health, AdapterHealth):
            return AdapterHealth("unavailable", "specialist returned an invalid health response")
        return health

    def health_status(self) -> dict[str, Any]:
        """Return bounded, independent health diagnostics for registered specialists."""
        registry = self._coordinator.registry
        capabilities = tuple(registry.capability_ids())
        disabled_modules = getattr(registry, "disabled_modules", lambda: {})()
        specialists: dict[str, dict[str, str]] = {}
        health_results: dict[str, AdapterHealth] = {}

        module_ids = ("chat", "code", "vision", "creative", "models")
        adapters = {module_id: registry.adapter(module_id) for module_id in module_ids}
        registered = {module_id: adapter for module_id, adapter in adapters.items() if adapter is not None}
        with ThreadPoolExecutor(max_workers=max(1, len(registered))) as executor:
            checked_health = dict(zip(registered, executor.map(self._adapter_health, registered.values())))

        for module_id in module_ids:
            adapter = adapters[module_id]
            if adapter is None:
                specialists[module_id] = {
                    "status": "disabled",
                    "reason": disabled_modules.get(module_id, "The specialist is not registered."),
                }
                continue

            health = checked_health[module_id]
            health_results[module_id] = health
            specialist = {"status": health.status}
            if health.detail:
                specialist["reason"] = health.detail
            specialists[module_id] = specialist

        gateway_health = health_results.get("chat")
        gateway_status = gateway_health.status if gateway_health is not None else "unavailable"
        return {
            "status": "ok" if capabilities and health_results and all(item.status == "healthy" for item in health_results.values()) else "degraded",
            "app": "SITA",
            "api_version": "1.0",
            "capability_count": len(capabilities),
            "capabilities": list(capabilities),
            "model_runtime": "omniroute",
            "specialists": specialists,
            "model_gateway": {"provider": "omniroute", "status": gateway_status},
        }

    def skill_catalogue(self) -> dict[str, Any]:
        """Return safe, display-only metadata for installed skill packs."""
        from tara_app.skills.loader import default_skills_root, list_skill_packs

        packs = list_skill_packs(skills_root=default_skills_root())
        return {
            "status": "available",
            "skills": [
                {
                    "name": pack.name,
                    "title": pack.title,
                    "description": pack.description,
                    "version": pack.version,
                    "tags": list(pack.tags),
                }
                for pack in packs
            ],
        }

    def model_catalogue(self) -> dict[str, Any]:
        adapter = self._coordinator.registry.adapter("models")
        if adapter is None:
            return {
                "status": "unavailable",
                "provider": "omniroute",
                "service_available": False,
                "models": [],
                "pull": {"status": "disabled", "message": "Model lifecycle is managed by OmniRoute."},
            }
        request = ModuleRequest(
            request_id="tara-model-catalog",
            session_id="tara-model-catalog",
            module="models",
            action="catalog",
            inputs={},
            timeout_seconds=min(adapter.timeout_seconds, 10),
        )
        try:
            result = adapter.execute(request)
        except Exception:
            result = None
        if result is None or result.status != "success":
            return {
                "status": "unavailable",
                "provider": "omniroute",
                "service_available": False,
                "models": [],
                "error": "OmniRoute model catalogue is unavailable",
                "pull": {"status": "disabled", "message": "Model lifecycle is managed by OmniRoute."},
            }
        models = result.data.get("models", []) if isinstance(result.data, Mapping) else []
        if not isinstance(models, list):
            models = []
        return {
            "status": "available",
            "provider": "omniroute",
            "service_available": True,
            "models": models,
            "pull": {"status": "disabled", "message": "Model lifecycle is managed by OmniRoute."},
        }

    def model_lifecycle_action(self, action: str, specialist: str) -> dict[str, Any] | None:
        """Run a configured local lifecycle action, if one is explicitly present."""
        catalogue = self._coordinator.model_catalog
        if catalogue is None:
            return None
        actions = {
            "pull": catalogue.start_pull,
            "unload": catalogue.unload_model,
            "remove": catalogue.remove_model,
        }
        handler = actions.get(action)
        if handler is None:
            raise ValueError("unsupported model lifecycle action")
        return handler(specialist)

    def prepare_runtime(self) -> str | None:
        """Run optional legacy catalogue startup hooks when a runtime provides them."""
        catalogue = getattr(self._coordinator, "model_catalog", None)
        if catalogue is None:
            return None
        catalogue.ensure_service_started()
        if "chat" not in catalogue.profiles:
            return None
        print("Preparing SITA's local chat model before the app opens.", flush=True)
        try:
            catalogue.ensure_model_installed("chat")
            catalogue.preload_model("chat", keep_alive="15m")
        except RuntimeError:
            return "SITA will start, but the chat model could not be prepared. Check the Models panel."
        print("SITA's chat model is ready.", flush=True)
        return None

    def close(self) -> None:
        """Release optional runtime resources during interface shutdown."""
        catalogue = getattr(self._coordinator, "model_catalog", None)
        if catalogue is not None:
            catalogue.close()

    def replace_conversation_history(self, session_id: str, history: Sequence[Mapping[str, str]]) -> None:
        self._coordinator.replace_conversation_history(session_id, history)

    def handle_question(
        self,
        question: str,
        *,
        session_id: str = "default",
        attachments: Sequence[Mapping[str, str]] = (),
        workspace_root: str | None = None,
        request_id: str | None = None,
        skill: str | None = None,
    ) -> Any:
        skill_prompt = None
        if skill is not None:
            if not isinstance(skill, str) or not skill.strip() or len(skill) > 64:
                raise ValueError("skill name is invalid")
            from tara_app.skills.loader import default_skills_root, load_skill_pack

            skill_prompt = load_skill_pack(
                skill.strip(), skills_root=default_skills_root()
            ).prompt_block()
        request = {
            "session_id": session_id,
            "attachments": attachments,
            "workspace_root": workspace_root,
            "request_id": request_id,
        }
        if skill_prompt is not None:
            request["skill_prompt"] = skill_prompt
        return self._coordinator.handle_question(question, **request)

    def list_skills(self) -> list[dict[str, str]]:
        """Return available skill pack summaries (instructions not expanded)."""
        try:
            from tara_app.skills.loader import default_skills_root, list_skill_packs

            packs = list_skill_packs(skills_root=default_skills_root())
        except Exception:
            return []
        return [
            {
                "name": pack.name,
                "title": pack.title,
                "description": pack.description,
                "version": pack.version,
            }
            for pack in packs
        ]

    def approve(self, approval_id: str, *, session_id: str) -> Any:
        return self._coordinator.approve(approval_id, session_id=session_id)

    def cancel_approval(self, approval_id: str, *, session_id: str) -> Any:
        return self._coordinator.cancel_approval(approval_id, session_id=session_id)

    def mcp_catalogue(self) -> dict[str, Any]:
        """Return display-safe MCP integration metadata for the manager UI."""
        from tara_app.mcp_catalogue import list_mcp_integrations

        return list_mcp_integrations()

    def mcp_status(self) -> dict[str, Any]:
        return self._coordinator.mcp_status()

    def list_mcp_tools(self, server_name: str | None = None) -> list[dict[str, Any]]:
        return self._coordinator.list_mcp_tools(server_name)

    def issue_mcp_approval_token(
        self,
        server_name: str,
        tool_name: str,
        arguments: Mapping[str, Any] | None,
        *,
        session_id: str,
    ) -> str:
        return self._coordinator.issue_mcp_approval_token(
            server_name, tool_name, arguments, session_id=session_id
        )

    def call_mcp_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Mapping[str, Any] | None,
        *,
        approval_token: str,
        session_id: str,
    ) -> str:
        return self._coordinator.call_mcp_tool(
            server_name, tool_name, arguments,
            approval_token=approval_token, session_id=session_id,
        )
