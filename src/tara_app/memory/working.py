"""Bounded, session-local working memory."""

from __future__ import annotations

from collections import OrderedDict

from .models import MemoryKind, MemoryRecord


class WorkingMemory:
    """Capacity-bounded recency store; it never writes to disk."""

    def __init__(self, capacity: int = 32) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
            raise ValueError("capacity must be a positive integer")
        self.capacity = capacity
        self._records: OrderedDict[str, MemoryRecord] = OrderedDict()

    def add(self, record: MemoryRecord) -> None:
        if record.kind is not MemoryKind.WORKING:
            raise ValueError("working memory accepts only WORKING records")
        self._records.pop(record.memory_id, None)
        self._records[record.memory_id] = record
        while len(self._records) > self.capacity:
            self._records.popitem(last=False)

    def get(self, memory_id: str) -> MemoryRecord | None:
        record = self._records.get(memory_id)
        if record is not None:
            self._records.move_to_end(memory_id)
        return record

    def recent(self, limit: int | None = None) -> tuple[MemoryRecord, ...]:
        if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 0):
            raise ValueError("limit must be a non-negative integer")
        records = tuple(self._records.values())
        return records if limit is None else records[-limit:] if limit else ()

    def remove(self, memory_id: str) -> MemoryRecord | None:
        return self._records.pop(memory_id, None)

    def clear(self) -> None:
        self._records.clear()

    def __len__(self) -> int:
        return len(self._records)
