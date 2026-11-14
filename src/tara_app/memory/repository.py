"""SQLite persistence port for episodic and semantic SN-86B memories.

Writes are denied unless the application injects an approval callback. The
repository does not interpret or mint SITA approval tokens; the existing
permission/approval layer remains responsible for authorizing the operation.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Protocol

from .models import MemoryKind, MemoryRecord, MemorySearchResult

_TOKEN_RE = re.compile(r"[a-z0-9_]+")


class MemoryRepository(Protocol):
    """Storage contract used by the memory engine."""

    def upsert(self, record: MemoryRecord) -> None: ...
    def delete(self, memory_id: str) -> bool: ...
    def search(
        self,
        query: str,
        *,
        kind: MemoryKind | None = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> tuple[MemorySearchResult, ...]: ...


class SQLiteMemoryRepository:
    """Durable local repository with explicit write authorization."""

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        authorize_write: Callable[[], bool] | None = None,
    ) -> None:
        configured = os.environ.get("TARA_MEMORY_DB", "").strip()
        self.path = (
            Path(path)
            if path is not None
            else Path(configured).expanduser()
            if configured
            else Path.home() / ".tara" / "memory.sqlite3"
        )
        self._authorize_write = authorize_write or (lambda: False)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._database() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS tn86_memories (
                    memory_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL CHECK(kind IN ('episodic', 'semantic')),
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    importance REAL NOT NULL,
                    tags_json TEXT NOT NULL,
                    source TEXT NOT NULL
                )
                """
            )
            # Keep historical TN-prefixed table/index names for existing database compatibility.
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_tn86_memories_kind_time "
                "ON tn86_memories(kind, created_at DESC)"
            )

    @contextmanager
    def _database(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def _require_approval(self) -> None:
        if not self._authorize_write():
            raise PermissionError("memory write requires SITA approval")

    def upsert(self, record: MemoryRecord) -> None:
        self._require_approval()
        if record.kind is MemoryKind.WORKING:
            raise ValueError("working memory must remain session-local")
        with self._database() as db:
            db.execute(
                """
                INSERT INTO tn86_memories
                    (memory_id, kind, content, created_at, importance, tags_json, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    kind=excluded.kind,
                    content=excluded.content,
                    importance=excluded.importance,
                    tags_json=excluded.tags_json,
                    source=excluded.source
                """,
                (
                    record.memory_id,
                    record.kind.value,
                    record.content,
                    record.created_at,
                    record.importance,
                    json.dumps(record.tags),
                    record.source,
                ),
            )

    def delete(self, memory_id: str) -> bool:
        self._require_approval()
        with self._database() as db:
            cursor = db.execute(
                "DELETE FROM tn86_memories WHERE memory_id = ?",
                (memory_id,),
            )
            return cursor.rowcount == 1

    def search(
        self,
        query: str,
        *,
        kind: MemoryKind | None = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> tuple[MemorySearchResult, ...]:
        if not isinstance(query, str) or not query.strip() or len(query) > 500:
            raise ValueError("query must contain 1 to 500 characters")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if not 0.0 <= min_score <= 1.0:
            raise ValueError("min_score must be in [0, 1]")
        if kind is MemoryKind.WORKING:
            return ()

        tokens = set(_TOKEN_RE.findall(query.lower()))
        if not tokens:
            return ()
        with self._database() as db:
            if kind is None:
                rows = db.execute(
                    "SELECT * FROM tn86_memories ORDER BY created_at DESC, memory_id"
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM tn86_memories WHERE kind = ? "
                    "ORDER BY created_at DESC, memory_id",
                    (kind.value,),
                ).fetchall()

        ranked: list[MemorySearchResult] = []
        for row in rows:
            candidate_tokens = set(
                _TOKEN_RE.findall((row["content"] + " " + " ".join(json.loads(row["tags_json"]))).lower())
            )
            score = len(tokens & candidate_tokens) / len(tokens)
            if score < min_score or score == 0.0:
                continue
            record = MemoryRecord(
                memory_id=row["memory_id"],
                kind=MemoryKind(row["kind"]),
                content=row["content"],
                created_at=row["created_at"],
                importance=row["importance"],
                tags=tuple(json.loads(row["tags_json"])),
                source=row["source"],
            )
            ranked.append(MemorySearchResult(record=record, score=score))

        ranked.sort(
            key=lambda item: (
                -item.score,
                -item.record.importance,
                -item.record.created_at,
                item.record.memory_id,
            )
        )
        return tuple(ranked[:limit])
