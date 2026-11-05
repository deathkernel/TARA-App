"""Application boundary shared by every TARA interface.

The facade hides the coordinator, registry, adapters and integration details
from HTTP, desktop and CLI transports. It is intentionally thin in this first
migration slice; workflow persistence and durable application state follow in
later steps.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from tara_app.contracts import ModuleRequest


class ApplicationFacade:
    """Stable use-case boundary for local TARA interfaces."""

    def __init__(self, coordinator: Any) -> None:
        self._coordinator = coordinator

    def health_status(self) -> dict[str, Any]:
        registry = self._coordinator.registry
        capabilities = tuple(registry.capability_ids())
        chat_adapter = registry.adapter("chat")
        gateway_health = None
        if chat_adapter is not None:
            try:
                gateway_health = chat_adapter.health()
            except Exception:
                gateway_health = None
        gateway_status = gateway_health.status if gateway_health is not None else "unavailable"
        disabled_modules = getattr(registry, "disabled_modules", lambda: {})()
        specialists: dict[str, dict[str, str]] = {}
        for module_id in ("chat", "code", "vision", "creative", "models"):
            adapter = registry.adapter(module_id)
            if adapter is None:
                specialists[module_id] = {
                    "status": "disabled",
                    "reason": disabled_modules.get(module_id, "The specialist is not registered."),
                }
            else:
                specialists[module_id] = {"status": "configured"}
        if chat_adapter is not None and gateway_status != "healthy":
            specialists["chat"] = {
                "status": "unavailable",
                "reason": "The Chat specialist is configured, but its authenticated OmniRoute model-catalogue check failed.",
            }
        return {
            "status": "ok" if capabilities and gateway_status == "healthy" else "degraded",
            "app": "TARA-App",
            "api_version": "1.0",
            "capability_count": len(capabilities),
            "capabilities": list(capabilities),
            "model_runtime": "omniroute",
            "specialists": specialists,
            "model_gateway": {"provider": "omniroute", "status": gateway_status},
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
        print("Preparing TARA's local chat model before the app opens.", flush=True)
        try:
            catalogue.ensure_model_installed("chat")
            catalogue.preload_model("chat", keep_alive="15m")
        except RuntimeError:
            return "TARA-App will start, but the chat model could not be prepared. Check the Models panel."
        print("TARA's chat model is ready.", flush=True)
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
    ) -> Any:
        return self._coordinator.handle_question(
            question,
            session_id=session_id,
            attachments=attachments,
            workspace_root=workspace_root,
            request_id=request_id,
        )

    def approve(self, approval_id: str, *, session_id: str) -> Any:
        return self._coordinator.approve(approval_id, session_id=session_id)

    def cancel_approval(self, approval_id: str, *, session_id: str) -> Any:
        return self._coordinator.cancel_approval(approval_id, session_id=session_id)

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
