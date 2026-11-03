"""Tests for the headless application service facade."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tara_app.application_service import ApplicationServiceError, TARAApplicationService
from tara_app.audit import JsonlAuditLog
from tara_app.contracts import ModelInfo
from tara_app.model_catalogue import ModelCatalogue
from tara_app.sessions import SessionStore


class FakeRuntime:
    def list_models(self, provider_id="ollama"):
        return [ModelInfo(provider_id, "test-model", family="test")]

    def chat(self, model, messages, provider_id="ollama"):
        return "reply:" + messages[-1]["content"]


class ApplicationServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.audit = JsonlAuditLog(Path(self.temp.name) / "audit.jsonl")
        self.catalogue = ModelCatalogue()
        self.service = TARAApplicationService(
            runtime=FakeRuntime(), audit=self.audit, sessions=SessionStore(),
            catalogue=self.catalogue,
        )

    def test_refresh_and_chat_use_catalogue_and_session(self):
        self.assertEqual(self.service.refresh_model_catalogue(), 1)
        session = self.service.create_session()
        turn = self.service.chat(
            session_id=session.session_id, provider_id="ollama",
            model="test-model", message="hello",
        )
        self.assertEqual(turn.assistant_message, "reply:hello")
        self.assertEqual([m.role for m in self.service.sessions.history(session.session_id)],
                         ["user", "assistant"])

    def test_chat_requires_catalogued_model_and_nonempty_message(self):
        session = self.service.create_session()
        with self.assertRaises(ApplicationServiceError):
            self.service.chat(session_id=session.session_id, provider_id="ollama",
                              model="missing", message="hello")
        with self.assertRaises(ApplicationServiceError):
            self.service.chat(session_id=session.session_id, provider_id="ollama",
                              model="missing", message=" ")


    def test_provider_failure_does_not_commit_partial_user_turn(self):
        class FailingRuntime(FakeRuntime):
            def chat(self, model, messages, provider_id="ollama"):
                raise RuntimeError("provider unavailable")

        self.service.runtime = FailingRuntime()
        self.service.refresh_model_catalogue()
        session = self.service.create_session()

        with self.assertRaises(ApplicationServiceError):
            self.service.chat(
                session_id=session.session_id, provider_id="ollama",
                model="test-model", message="first attempt",
            )

        self.assertEqual(self.service.sessions.history(session.session_id), [])

    def test_empty_provider_response_does_not_commit_partial_user_turn(self):
        class EmptyRuntime(FakeRuntime):
            def chat(self, model, messages, provider_id="ollama"):
                return "  "

        self.service.runtime = EmptyRuntime()
        self.service.refresh_model_catalogue()
        session = self.service.create_session()

        with self.assertRaises(ApplicationServiceError):
            self.service.chat(
                session_id=session.session_id, provider_id="ollama",
                model="test-model", message="first attempt",
            )

        self.assertEqual(self.service.sessions.history(session.session_id), [])


    def test_service_can_opt_into_persistent_sessions(self):
        database = Path(self.temp.name) / "service-sessions.sqlite3"
        first = TARAApplicationService(
            runtime=FakeRuntime(), audit=self.audit, session_database_path=database,
        )
        session = first.create_session({"source": "test"})
        first.sessions.append_message(session.session_id, "user", "persist this")

        restarted = TARAApplicationService(
            runtime=FakeRuntime(), audit=self.audit, session_database_path=database,
        )
        self.assertEqual(restarted.sessions.get(session.session_id).metadata, {"source": "test"})
        self.assertEqual(restarted.sessions.history(session.session_id)[0].content, "persist this")

    def test_service_rejects_ambiguous_session_storage_configuration(self):
        with self.assertRaises(ValueError):
            TARAApplicationService(
                runtime=FakeRuntime(), audit=self.audit,
                sessions=SessionStore(), session_database_path=Path(self.temp.name) / "sessions.sqlite3",
            )

    def test_close_session(self):
        session = self.service.create_session()
        self.assertTrue(self.service.close_session(session.session_id))
        self.assertFalse(self.service.close_session(session.session_id))


if __name__ == "__main__":
    unittest.main()
