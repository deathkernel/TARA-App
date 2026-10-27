"""In-memory session store with bounded history and per-session isolation."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4
from typing import Any


class SessionError(RuntimeError):
    """Raised when a session operation violates its bounds or state."""


@dataclass(frozen=True)
class SessionMessage:
    role: str
    content: str
    created_at: str


@dataclass
class Session:
    session_id: str
    created_at: str
    updated_at: str
    metadata: dict[str, str] = field(default_factory=dict)
    messages: list[SessionMessage] = field(default_factory=list)


class SessionStore:
    """Process-local sessions; deliberately does not persist chat content to disk."""

    def __init__(self, *, max_sessions: int = 100, max_messages_per_session: int = 40,
                 max_content_chars: int = 16_000) -> None:
        for name, value in (("max_sessions", max_sessions),
                            ("max_messages_per_session", max_messages_per_session),
                            ("max_content_chars", max_content_chars)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        self.max_sessions = max_sessions
        self.max_messages_per_session = max_messages_per_session
        self.max_content_chars = max_content_chars
        self._sessions: dict[str, Session] = {}
        self._lock = RLock()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create(self, metadata: dict[str, str] | None = None) -> Session:
        if metadata is not None and (
            not isinstance(metadata, dict)
            or any(not isinstance(k, str) or not isinstance(v, str) for k, v in metadata.items())
        ):
            raise SessionError("session metadata must contain string keys and values")
        with self._lock:
            if len(self._sessions) >= self.max_sessions:
                raise SessionError("session capacity reached; close a session before creating another")
            now = self._now()
            session = Session(str(uuid4()), now, now, dict(metadata or {}))
            self._sessions[session.session_id] = session
            return self._snapshot(session)

    def get(self, session_id: str) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionError("session not found")
            return self._snapshot(session)

    def append_message(self, session_id: str, role: str, content: str) -> SessionMessage:
        if role not in {"system", "user", "assistant", "tool"}:
            raise SessionError("role is not supported")
        if not isinstance(content, str) or not content.strip():
            raise SessionError("message content must be a non-empty string")
        if len(content) > self.max_content_chars:
            raise SessionError("message exceeds configured character limit")
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionError("session not found")
            if len(session.messages) >= self.max_messages_per_session:
                raise SessionError("session message capacity reached")
            message = SessionMessage(role, content, self._now())
            session.messages.append(message)
            session.updated_at = message.created_at
            return message

    def history(self, session_id: str, *, limit: int | None = None) -> list[SessionMessage]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionError("session not found")
            if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
                raise ValueError("limit must be a positive integer")
            messages = session.messages if limit is None else session.messages[-limit:]
            return list(messages)

    def close(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"session_id": s.session_id, "created_at": s.created_at,
                 "updated_at": s.updated_at, "message_count": len(s.messages),
                 "metadata": dict(s.metadata)}
                for s in self._sessions.values()
            ]

    @staticmethod
    def _snapshot(session: Session) -> Session:
        return Session(session.session_id, session.created_at, session.updated_at,
                       dict(session.metadata), list(session.messages))
