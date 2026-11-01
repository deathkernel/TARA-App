"""Tests for bounded, isolated in-memory sessions."""
import sys
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tara_app.sessions import SessionError, SessionStore  # noqa: E402


class SessionStoreTests(unittest.TestCase):
    def test_sessions_are_isolated(self):
        store = SessionStore()
        first = store.create()
        second = store.create()
        store.append_message(first.session_id, "user", "first secret")
        self.assertEqual(len(store.history(second.session_id)), 0)
        self.assertEqual(store.history(first.session_id)[0].content, "first secret")

    def test_message_and_session_limits_are_enforced(self):
        store = SessionStore(max_sessions=1, max_messages_per_session=1, max_content_chars=5)
        session = store.create()
        with self.assertRaises(SessionError):
            store.create()
        with self.assertRaises(SessionError):
            store.append_message(session.session_id, "user", "too long")
        store.append_message(session.session_id, "user", "hello")
        with self.assertRaises(SessionError):
            store.append_message(session.session_id, "assistant", "again")


    def test_append_turn_commits_user_and_assistant_as_a_pair(self):
        """Verify an in-memory turn is stored in user-then-assistant order."""
        store = SessionStore(max_messages_per_session=2)
        session = store.create()

        user_message, assistant_message = store.append_turn(
            session.session_id, "hello", "hello back"
        )

        self.assertEqual((user_message.role, assistant_message.role), ("user", "assistant"))
        self.assertEqual(
            [(message.role, message.content) for message in store.history(session.session_id)],
            [("user", "hello"), ("assistant", "hello back")],
        )

    def test_append_turn_persists_both_messages_together(self):
        """Verify a complete turn survives a SQLite-backed store restart."""
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "sessions.sqlite3"
            store = SessionStore(database_path=database)
            session = store.create()
            store.append_turn(session.session_id, "hello", "hello back")

            restarted = SessionStore(database_path=database)
            self.assertEqual(
                [(message.role, message.content) for message in restarted.history(session.session_id)],
                [("user", "hello"), ("assistant", "hello back")],
            )

    def test_append_turn_rejects_insufficient_capacity_without_partial_write(self):
        """Verify insufficient capacity rejects the pair without writing either message."""
        store = SessionStore(max_messages_per_session=1)
        session = store.create()

        with self.assertRaisesRegex(SessionError, "two message slots"):
            store.append_turn(session.session_id, "hello", "hello back")

        self.assertEqual(store.history(session.session_id), [])

    def test_opt_in_persistence_restores_sessions_and_messages(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "sessions.sqlite3"
            first_store = SessionStore(database_path=database)
            session = first_store.create({"purpose": "test"})
            first_store.append_message(session.session_id, "user", "private test prompt")
            first_store.append_message(session.session_id, "assistant", "private test answer")

            restarted_store = SessionStore(database_path=database)
            restored = restarted_store.get(session.session_id)
            self.assertEqual(restored.metadata, {"purpose": "test"})
            self.assertEqual(
                [(message.role, message.content) for message in restarted_store.history(session.session_id)],
                [("user", "private test prompt"), ("assistant", "private test answer")],
            )

            self.assertTrue(restarted_store.close(session.session_id))
            after_close = SessionStore(database_path=database)
            with self.assertRaises(SessionError):
                after_close.get(session.session_id)

    def test_persistence_is_disabled_by_default(self):
        store = SessionStore()
        session = store.create()
        self.assertIsNone(store.database_path)
        self.assertEqual(store.history(session.session_id), [])

    def test_unknown_session_and_invalid_role_rejected(self):
        store = SessionStore()
        with self.assertRaises(SessionError):
            store.history("missing")
        session = store.create()
        with self.assertRaises(SessionError):
            store.append_message(session.session_id, "root", "not allowed")

    def test_close_removes_session(self):
        store = SessionStore()
        session = store.create()
        self.assertTrue(store.close(session.session_id))
        self.assertFalse(store.close(session.session_id))
        with self.assertRaises(SessionError):
            store.get(session.session_id)


    def test_retention_is_disabled_by_default_and_preserves_old_sessions(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "sessions.sqlite3"
            store = SessionStore(database_path=database)
            session = store.create()
            with sqlite3.connect(database) as db:
                old = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
                db.execute("UPDATE sessions SET updated_at = ? WHERE session_id = ?", (old, session.session_id))

            restarted = SessionStore(database_path=database)
            self.assertEqual(restarted.get(session.session_id).session_id, session.session_id)

    def test_explicit_retention_prunes_expired_sessions_and_cascades_messages(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "sessions.sqlite3"
            store = SessionStore(database_path=database)
            expired = store.create()
            active = store.create()
            store.append_message(expired.session_id, "user", "expired content")
            with sqlite3.connect(database) as db:
                old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
                db.execute("UPDATE sessions SET updated_at = ? WHERE session_id = ?", (old, expired.session_id))

            restarted = SessionStore(database_path=database, retention_seconds=7 * 24 * 60 * 60)
            with self.assertRaises(SessionError):
                restarted.get(expired.session_id)
            self.assertEqual(restarted.get(active.session_id).session_id, active.session_id)
            with sqlite3.connect(database) as db:
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM session_messages WHERE session_id = ?", (expired.session_id,)).fetchone()[0],
                    0,
                )
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 1)

    def test_manual_retention_prune_uses_updated_at_and_keeps_recent_sessions(self):
        store = SessionStore(retention_seconds=60)
        old = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        with patch.object(SessionStore, "_now", return_value=old):
            expired = store.create()
        active = store.create()

        removed = store.prune_expired_sessions()

        self.assertEqual(removed, 1)
        with self.assertRaises(SessionError):
            store.get(expired.session_id)
        self.assertEqual(store.get(active.session_id).session_id, active.session_id)

    def test_retention_configuration_must_be_a_positive_integer(self):
        for value in (0, -1, True, 1.5, "3600"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                SessionStore(retention_seconds=value)

    def test_retention_rejects_naive_reference_time(self):
        store = SessionStore(retention_seconds=60)
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            store.prune_expired_sessions(now=datetime(2026, 1, 1))

    def test_future_database_schema_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "sessions.sqlite3"
            with sqlite3.connect(database) as db:
                db.execute("PRAGMA user_version = 99")
            with self.assertRaisesRegex(SessionError, "schema is newer"):
                SessionStore(database_path=database)


if __name__ == "__main__":
    unittest.main()
