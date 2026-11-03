"""Explicit consent-based local memory storage."""
from __future__ import annotations
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

MODULE_ID = "memory"
CAPABILITIES = ("search", "store", "forget")
_MAX_QUERY = 500
_MAX_KEY = 120
_MAX_VALUE = 2000
_MAX_RESULTS = 20

class MemoryStore:
    def __init__(self, path: str | Path | None = None) -> None:
        configured = os.environ.get("TARA_MEMORY_DB", "").strip()
        self.path = Path(path) if path is not None else (Path(configured).expanduser() if configured else Path.home() / ".tara" / "memory.sqlite3")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._database() as db:
            db.execute("CREATE TABLE IF NOT EXISTS memories (key TEXT PRIMARY KEY, value TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")

    @contextmanager
    def _database(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def search(self, query: str, limit: int = 10) -> list[dict[str, str]]:
        if not isinstance(query, str) or not query.strip() or len(query) > _MAX_QUERY:
            raise ValueError("query must contain 1 to 500 characters")
        words = [word for word in query.split() if word][:20]
        clause = " AND ".join("(instr(lower(key), lower(?)) > 0 OR instr(lower(value), lower(?)) > 0)" for _ in words)
        params = [item for word in words for item in (word, word)]
        with self._database() as db:
            rows = db.execute(f"SELECT key, value, updated_at FROM memories WHERE {clause} ORDER BY updated_at DESC, key LIMIT ?", (*params, max(1, min(limit, _MAX_RESULTS)))).fetchall()
        return [dict(row) for row in rows]

    def store(self, key: str, value: str) -> None:
        if not isinstance(key, str) or not key.strip() or len(key) > _MAX_KEY:
            raise ValueError("key must contain 1 to 120 characters")
        if not isinstance(value, str) or not value.strip() or len(value) > _MAX_VALUE:
            raise ValueError("value must contain 1 to 2000 characters")
        with self._database() as db:
            db.execute("INSERT INTO memories(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP", (key.strip(), value.strip()))

    def forget(self, key: str) -> bool:
        if not isinstance(key, str) or not key.strip() or len(key) > _MAX_KEY:
            raise ValueError("key must contain 1 to 120 characters")
        with self._database() as db:
            cursor = db.execute("DELETE FROM memories WHERE key = ?", (key.strip(),))
            return cursor.rowcount == 1

def execute(action: str, inputs: dict[str, Any], *, approval_token: str | None = None) -> tuple[str, dict[str, Any], str | None]:
    if action not in CAPABILITIES:
        return "permission_denied", {}, "unsupported memory capability"
    if action in {"store", "forget"} and (not isinstance(approval_token, str) or not approval_token.strip()):
        return "approval_required", {}, "memory changes require an approval token"
    store = MemoryStore()
    if action == "search":
        query = inputs.get("query", inputs.get("question", ""))
        return "success", {"memories": store.search(query)}, None
    if action == "store":
        key, value = inputs.get("key"), inputs.get("value")
        store.store(key, value)
        return "success", {"stored": True, "key": key.strip()}, None
    key = inputs.get("key")
    if not isinstance(key, str):
        raise ValueError("key must be text")
    return "success", {"forgotten": store.forget(key), "key": key.strip()}, None

