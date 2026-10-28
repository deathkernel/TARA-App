"""Application service coordinating sessions, local models, permissions, and audit."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tara_app.audit import AuditLogError, JsonlAuditLog
from tara_app.model_catalogue import ModelCatalogue
from tara_app.orchestration import CapabilityOrchestrator, CapabilityRequest, CapabilityResponse
from tara_app.runtime_manager import RuntimeManager, RuntimeConfigurationError
from tara_app.sessions import Session, SessionError, SessionStore


class ApplicationServiceError(RuntimeError):
    """Raised when an application-level operation cannot be completed."""


@dataclass(frozen=True)
class ChatTurn:
    session_id: str
    provider_id: str
    model: str
    user_message: str
    assistant_message: str


class TARAApplicationService:
    """Headless app facade; UI layers should call this instead of providers directly."""

    def __init__(
        self,
        *,
        runtime: RuntimeManager,
        audit: JsonlAuditLog,
        sessions: SessionStore | None = None,
        catalogue: ModelCatalogue | None = None,
        orchestrator: CapabilityOrchestrator | None = None,
        session_database_path: str | Path | None = None,
    ) -> None:
        self.runtime = runtime
        self.audit = audit
        if sessions is not None and session_database_path is not None:
            raise ValueError("pass either sessions or session_database_path, not both")
        self.sessions = sessions or SessionStore(database_path=session_database_path)
        self.catalogue = catalogue or ModelCatalogue()
        self.orchestrator = orchestrator

    def create_session(self, metadata: dict[str, str] | None = None) -> Session:
        try:
            session = self.sessions.create(metadata)
            self.audit.record("session_created", {"session_id": session.session_id, "metadata": metadata or {}})
            return session
        except (SessionError, AuditLogError) as exc:
            # If audit persistence fails, do not leave an untracked session behind.
            if "session" in locals():
                self.sessions.close(session.session_id)
            raise ApplicationServiceError("session could not be created safely") from None

    def refresh_model_catalogue(self, provider_id: str = "ollama") -> int:
        try:
            models = self.runtime.list_models(provider_id)
            existing = [model for model in self.catalogue.list() if model.provider_id != provider_id]
            self.catalogue.replace(existing + models)
            self.audit.record("model_catalogue_refreshed", {
                "provider_id": provider_id, "model_count": len(models)
            })
            return len(models)
        except (RuntimeConfigurationError, AuditLogError, ValueError):
            raise ApplicationServiceError("model catalogue refresh failed") from None

    def list_models(self, provider_id: str | None = None) -> list[dict[str, Any]]:
        models = self.catalogue.list()
        if provider_id is not None:
            models = [model for model in models if model.provider_id == provider_id]
        return [
            {"provider_id": model.provider_id, "name": model.name, "size_bytes": model.size_bytes,
             "family": model.family, "parameter_size": model.parameter_size,
             "quantization_level": model.quantization_level, "model_format": model.model_format}
            for model in models
        ]

    def chat(self, *, session_id: str, provider_id: str, model: str, message: str) -> ChatTurn:
        if not isinstance(message, str) or not message.strip():
            raise ApplicationServiceError("message must be non-empty")
        try:
            session = self.sessions.get(session_id)
            selected = self.catalogue.get(provider_id, model)
            if selected.provider_id != provider_id:
                raise ApplicationServiceError("selected model/provider mismatch")
            history = self.sessions.history(session_id)
            # Build the request with a tentative user turn. Commit both messages only
            # after the provider returns a usable response, so provider failures do not
            # leave an orphaned user message in the next turn's conversation context.
            request_history = [
                {"role": item.role, "content": item.content}
                for item in history if item.role in {"system", "user", "assistant"}
            ]
            request_history.append({"role": "user", "content": message})
            response = self.runtime.chat(
                model=model,
                provider_id=provider_id,
                messages=request_history,
            )
            if not isinstance(response, str) or not response.strip():
                raise ApplicationServiceError("chat provider returned an empty or invalid response")
            self.sessions.append_message(session_id, "user", message)
            self.sessions.append_message(session_id, "assistant", response.strip())
            self.audit.record("chat_turn_completed", {
                "session_id": session_id, "provider_id": provider_id, "model": model,
            })
            return ChatTurn(session_id, provider_id, model, message, response.strip())
        except ApplicationServiceError:
            raise
        except (SessionError, RuntimeConfigurationError, AuditLogError, ValueError, RuntimeError):
            raise ApplicationServiceError("chat turn failed; inspect local provider status and session state") from None

    def dispatch_capability(self, request: CapabilityRequest) -> CapabilityResponse:
        if self.orchestrator is None:
            raise ApplicationServiceError("capability orchestration is not configured")
        return self.orchestrator.dispatch(request)

    def close_session(self, session_id: str) -> bool:
        existed = self.sessions.close(session_id)
        if existed:
            try:
                self.audit.record("session_closed", {"session_id": session_id})
            except AuditLogError:
                # Session has been removed from memory; do not recreate it on logging failure.
                raise ApplicationServiceError("session closed but audit event could not be persisted") from None
        return existed
