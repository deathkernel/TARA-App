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

    def test_append_turn_commits_user_and_assistant_as_a_pair(self):
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

    def test_append_turn_is_atomic_when_capacity_is_insufficient(self):
        store = SessionStore(max_messages_per_session=1)
        session = store.create()

        with self.assertRaisesRegex(SessionError, "two message slots"):
            store.append_turn(session.session_id, "hello", "hello back")

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
