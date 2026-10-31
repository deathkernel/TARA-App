"""Tests for bounded, isolated in-memory sessions."""
import sys
import tempfile
import unittest
from pathlib import Path

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


    def test_replace_history_persists_and_evicts_oldest_session(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "sessions.sqlite3"
            store = SessionStore(database_path=database, max_sessions=1, max_messages_per_session=2)
            store.replace_history("session-one", [{"role": "user", "content": "first"}])
            store.replace_history("session-two", [{"role": "user", "content": "second"}])
            self.assertEqual([item["session_id"] for item in store.list_sessions()], ["session-two"])
            restarted = SessionStore(database_path=database, max_sessions=1, max_messages_per_session=2)
            self.assertEqual(restarted.history("session-two")[0].content, "second")
            with self.assertRaises(SessionError):
                restarted.get("session-one")

    def test_replace_history_rejects_oversized_or_invalid_entries(self):
        store = SessionStore(max_messages_per_session=1, max_content_chars=5)
        with self.assertRaises(SessionError):
            store.replace_history("session-a", [{"role": "user", "content": "too long"}])
        with self.assertRaises(SessionError):
            store.replace_history("session-a", [{"role": "system", "content": "hello"}])
        with self.assertRaises(SessionError):
            store.replace_history("session-a", [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "again"},
            ])

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


if __name__ == "__main__":
    unittest.main()
