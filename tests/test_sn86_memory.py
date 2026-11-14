"""Tests for SN-86 working, episodic, semantic and consolidation behavior."""

import pytest

from tara_app.memory import (
    MemoryEngine,
    MemoryKind,
    MemoryRecord,
    SQLiteMemoryRepository,
    WorkingMemory,
)


def make_repository(tmp_path, *, approved=True):
    return SQLiteMemoryRepository(
        tmp_path / "memory.sqlite3",
        authorize_write=lambda: approved,
    )


def test_working_memory_is_bounded_and_recency_ordered():
    working = WorkingMemory(capacity=2)
    for index in range(3):
        working.add(
            MemoryRecord(
                memory_id=str(index),
                kind=MemoryKind.WORKING,
                content=f"observation {index}",
                created_at=float(index),
            )
        )

    assert [item.memory_id for item in working.recent()] == ["1", "2"]
    assert working.get("1") is not None
    assert [item.memory_id for item in working.recent()] == ["2", "1"]


def test_working_memory_rejects_long_term_records():
    working = WorkingMemory()
    record = MemoryRecord(
        memory_id="semantic-1",
        kind=MemoryKind.SEMANTIC,
        content="SITA is a local-first assistant",
        created_at=1.0,
    )

    with pytest.raises(ValueError, match="WORKING"):
        working.add(record)


def test_capture_stays_ephemeral_until_consolidated(tmp_path):
    repository = make_repository(tmp_path)
    engine = MemoryEngine(repository)
    captured = engine.capture("User prefers concise technical explanations")

    assert captured.kind is MemoryKind.WORKING
    assert engine.working.get(captured.memory_id) is not None
    assert repository.search("concise explanations") == ()

    consolidated = engine.consolidate(
        captured.memory_id,
        target_kind=MemoryKind.SEMANTIC,
    )

    assert consolidated.kind is MemoryKind.SEMANTIC
    assert engine.working.get(captured.memory_id) is None
    assert repository.search("concise explanations")[0].record.memory_id == captured.memory_id


def test_consolidation_preserves_working_item_when_approval_is_denied(tmp_path):
    engine = MemoryEngine(make_repository(tmp_path, approved=False))
    captured = engine.capture("A useful task outcome")

    with pytest.raises(PermissionError, match="approval"):
        engine.consolidate(captured.memory_id, target_kind=MemoryKind.EPISODIC)

    assert engine.working.get(captured.memory_id) is not None


def test_episodic_and_semantic_memory_are_separately_retrievable(tmp_path):
    engine = MemoryEngine(make_repository(tmp_path))
    episodic = engine.remember(
        "Completed repository audit and fixed import issue",
        kind=MemoryKind.EPISODIC,
        tags=("engineering",),
    )
    semantic = engine.remember(
        "The project uses Python and SQLite for local persistence",
        kind=MemoryKind.SEMANTIC,
        tags=("architecture",),
    )

    assert engine.recall("repository audit", kinds=(MemoryKind.EPISODIC,))[0].record == episodic
    assert engine.recall("SQLite local persistence", kinds=(MemoryKind.SEMANTIC,))[0].record == semantic


def test_persistent_writes_and_deletes_require_authorization(tmp_path):
    repository = make_repository(tmp_path, approved=False)
    record = MemoryRecord(
        memory_id="blocked",
        kind=MemoryKind.EPISODIC,
        content="This must not be stored",
        created_at=1.0,
    )

    with pytest.raises(PermissionError, match="approval"):
        repository.upsert(record)
    with pytest.raises(PermissionError, match="approval"):
        repository.delete("blocked")
    assert repository.search("must not be stored") == ()


def test_repository_persists_records_across_instances(tmp_path):
    path = tmp_path / "memory.sqlite3"
    first = SQLiteMemoryRepository(path, authorize_write=lambda: True)
    record = MemoryRecord(
        memory_id="persisted",
        kind=MemoryKind.SEMANTIC,
        content="Memory survives process restarts",
        created_at=42.0,
        importance=0.9,
        tags=("durability",),
        source="test",
    )
    first.upsert(record)

    second = SQLiteMemoryRepository(path)
    assert second.search("process restarts")[0].record == record


def test_invalid_memory_kind_and_limits_are_rejected():
    with pytest.raises(ValueError, match="importance"):
        MemoryRecord(
            memory_id="invalid",
            kind=MemoryKind.SEMANTIC,
            content="bad importance",
            created_at=1.0,
            importance=1.5,
        )
    with pytest.raises(ValueError, match="capacity"):
        WorkingMemory(capacity=0)
