"""Bounded session store with optional, explicit SQLite persistence.

Chat content stays in memory by default. Persistence is opt-in via database_path.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
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
    """Bounded sessions; persistence is disabled unless a database path is supplied."""

    def __init__(
        self,
        *,
        max_sessions: int = 100,
        max_messages_per_session: int = 40,
        max_content_chars: int = 16_000,
        database_path: str | Path | None = None,
    ) -> None:
        for name, value in (
            ("max_sessions", max_sessions),
            ("max_messages_per_session", max_messages_per_session),
            ("max_content_chars", max_content_chars),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        self.max_sessions = max_sessions
        self.max_messages_per_session = max_messages_per_session
        self.max_content_chars = max_content_chars
        self.database_path = Path(database_path).expanduser().resolve() if database_path is not None else None
        self._sessions: dict[str, Session] = {}
        self._lock = RLock()
        if self.database_path is not None:
            try:
                self.database_path.parent.mkdir(parents=True, exist_ok=True)
                with self._connect() as db:
                    db.execute("""
                        CREATE TABLE IF NOT EXISTS sessions (
                            session_id TEXT PRIMARY KEY,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            metadata_json TEXT NOT NULL
                        )
                    """)
                    db.execute("""
                        CREATE TABLE IF NOT EXISTS session_messages (
                            session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                            position INTEGER NOT NULL,
                            role TEXT NOT NULL,
                            content TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            PRIMARY KEY (session_id, position)
                        )
                    """)
                    db.execute("PRAGMA foreign_keys = ON")
                    self._load_from_db(db)
                if os.name != "nt":
                    os.chmod(self.database_path, 0o600)
            except (OSError, sqlite3.Error, ValueError, TypeError):
                raise SessionError("persistent session store could not be initialized") from None

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        if self.database_path is None:
            raise SessionError("persistent session storage is not configured")
        db = sqlite3.connect(str(self.database_path), timeout=5.0)
        try:
            db.execute("PRAGMA foreign_keys = ON")
            with db:
                yield db
        finally:
            db.close()

    def _load_from_db(self, db: sqlite3.Connection) -> None:
        sessions = db.execute(
            "SELECT session_id, created_at, updated_at, metadata_json FROM sessions ORDER BY created_at"
        ).fetchall()
        if len(sessions) > self.max_sessions:
            raise SessionError("persistent session count exceeds configured capacity")
        for session_id, created_at, updated_at, metadata_json in sessions:
            metadata = json.loads(metadata_json)
            if not isinstance(metadata, dict) or any(
                not isinstance(k, str) or not isinstance(v, str) for k, v in metadata.items()
            ):
                raise SessionError("persistent session metadata is invalid")
            rows = db.execute(
                "SELECT role, content, created_at FROM session_messages WHERE session_id = ? ORDER BY position",
                (session_id,),
            ).fetchall()
            if len(rows) > self.max_messages_per_session or any(
                role not in {"system", "user", "assistant", "tool"}
                or not isinstance(content, str) or not content.strip()
                or len(content) > self.max_content_chars
                for role, content, _ in rows
            ):
                raise SessionError("persistent session messages exceed configured limits")
            self._sessions[session_id] = Session(
                session_id, created_at, updated_at, metadata,
                [SessionMessage(role, content, created) for role, content, created in rows],
            )

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
            if self.database_path is not None:
                try:
                    with self._connect() as db:
                        db.execute(
                            "INSERT INTO sessions(session_id, created_at, updated_at, metadata_json) VALUES (?, ?, ?, ?)",
                            (session.session_id, session.created_at, session.updated_at,
                             json.dumps(session.metadata, ensure_ascii=False, separators=(",", ":"))),
                        )
                except (sqlite3.Error, OSError):
                    raise SessionError("session could not be persisted") from None
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
            if self.database_path is not None:
                try:
                    with self._connect() as db:
                        position = len(session.messages)
                        db.execute(
                            "INSERT INTO session_messages(session_id, position, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                            (session_id, position, role, content, message.created_at),
                        )
                        db.execute(
                            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                            (message.created_at, session_id),
                        )
                except (sqlite3.Error, OSError):
                    raise SessionError("message could not be persisted") from None
            session.messages.append(message)
            session.updated_at = message.created_at
            return message

    def replace_history(self, session_id: str, messages: Sequence[Mapping[str, str]]) -> Session:
        """Replace a bounded conversation history, creating or retaining its session ID."""
        if not isinstance(session_id, str) or not session_id.strip() or len(session_id) > 128:
            raise SessionError("session ID is invalid")
        if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes)):
            raise SessionError("session history must be a sequence")
        if len(messages) > self.max_messages_per_session:
            raise SessionError("session message capacity reached")
        now = self._now()
        safe_messages: list[SessionMessage] = []
        for item in messages:
            if not isinstance(item, Mapping) or set(item) != {"role", "content"}:
                raise SessionError("session history entry is invalid")
            role, content = item.get("role"), item.get("content")
            if role not in {"user", "assistant"} or not isinstance(content, str) or not content.strip():
                raise SessionError("session history entry is invalid")
            if len(content) > self.max_content_chars:
                raise SessionError("message exceeds configured character limit")
            safe_messages.append(SessionMessage(role, content, now))

        with self._lock:
            existing = self._sessions.get(session_id)
            created_at = existing.created_at if existing is not None else now
            metadata = dict(existing.metadata) if existing is not None else {}
            session = Session(session_id, created_at, now, metadata, safe_messages)
            evicted_id: str | None = None
            if existing is None and len(self._sessions) >= self.max_sessions:
                evicted_id = min(self._sessions.values(), key=lambda value: value.updated_at).session_id
            if self.database_path is not None:
                try:
                    with self._connect() as db:
                        if evicted_id is not None:
                            db.execute("DELETE FROM sessions WHERE session_id = ?", (evicted_id,))
                        db.execute(
                            """INSERT INTO sessions(session_id, created_at, updated_at, metadata_json)
                               VALUES (?, ?, ?, ?)
                               ON CONFLICT(session_id) DO UPDATE SET updated_at = excluded.updated_at""",
                            (session_id, created_at, now, json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))),
                        )
                        db.execute("DELETE FROM session_messages WHERE session_id = ?", (session_id,))
                        db.executemany(
                            """INSERT INTO session_messages(session_id, position, role, content, created_at)
                               VALUES (?, ?, ?, ?, ?)""",
                            [(session_id, index, item.role, item.content, item.created_at)
                             for index, item in enumerate(safe_messages)],
                        )
                except (sqlite3.Error, OSError):
                    raise SessionError("session history could not be persisted") from None
            if evicted_id is not None:
                self._sessions.pop(evicted_id, None)
            self._sessions[session_id] = session
            return self._snapshot(session)

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
            if session_id not in self._sessions:
                return False
            if self.database_path is not None:
                try:
                    with self._connect() as db:
                        db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                except (sqlite3.Error, OSError):
                    raise SessionError("session could not be removed from persistent storage") from None
            self._sessions.pop(session_id, None)
            return True

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
