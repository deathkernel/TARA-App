"""Tests for bounded, isolated in-memory sessions."""
import sys
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
