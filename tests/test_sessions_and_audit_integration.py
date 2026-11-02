"""Integration tests for persistent sessions, audit logging, and web session APIs."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tara_app.audit import JsonlAuditLog
from tara_app.contracts import Capability, ModuleResult, RouteDecision
from tara_app.orchestrator import Orchestrator
from tara_app.registry import CapabilityRegistry
from tara_app.sessions import SessionStore
from tara_app.webapp import _Server


class FakeAdapter:
    def __init__(self, module_id: str, capabilities: tuple, result: ModuleResult):
        self.module_id = module_id
        self.capabilities = tuple(capabilities)
        self.result = result
        self.calls = []

    def health(self):
        from tara_app.contracts import AdapterHealth
        return AdapterHealth("healthy", "available")

    def execute(self, request):
        self.calls.append(request)
        return self.result


class FakeRouter:
    def __init__(self, decision: RouteDecision):
        self.decision = decision

    def route(self, _input):
        return self.decision


class SessionAndAuditIntegrationTests(unittest.TestCase):
    def test_orchestrator_sqlite_persistence_and_restart(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_sessions.sqlite3"
            audit_path = Path(temp_dir) / "test_audit.jsonl"

            chat_result = ModuleResult("success", {"text": "Persisted response"})
            chat_adapter = FakeAdapter(
                "chat",
                (Capability("chat", "respond", "Conversation", True),),
                chat_result,
            )
            registry = CapabilityRegistry()
            registry.register(chat_adapter)

            router = FakeRouter(
                RouteDecision("req-1", "routed", "chat", "respond", "conversation", "Chat intent")
            )
            store = SessionStore(database_path=db_path)
            audit = JsonlAuditLog(audit_path)

            app = Orchestrator(registry, router, sessions=store, audit=audit)

            # Ask question in session-1
            outcome = app.handle_question("Hello world", session_id="session-1", request_id="req-1")
            self.assertEqual(outcome.status, "success")

            # Check that session history in memory and DB is recorded
            history = app.get_conversation_history("session-1")
            self.assertEqual(len(history), 2)
            self.assertEqual(history[0]["content"], "Hello world")
            self.assertEqual(history[1]["content"], "Persisted response")

            # Verify audit log was recorded
            self.assertTrue(audit_path.is_file())
            audit_lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertGreaterEqual(len(audit_lines), 1)
            record = json.loads(audit_lines[0])
            self.assertEqual(record["event_type"], "chat_turn")
            self.assertEqual(record["fields"]["session_id"], "session-1")

            # Simulate restart with a fresh Orchestrator and fresh SessionStore loading the same DB
            restarted_store = SessionStore(database_path=db_path)
            restarted_app = Orchestrator(registry, router, sessions=restarted_store)

            restored_history = restarted_app.get_conversation_history("session-1")
            self.assertEqual(len(restored_history), 2)
            self.assertEqual(restored_history[0]["content"], "Hello world")
            self.assertEqual(restored_history[1]["content"], "Persisted response")

            # Check list_sessions and get_session
            sessions = restarted_app.list_sessions()
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["session_id"], "session-1")
            self.assertEqual(sessions[0]["message_count"], 2)

            session_detail = restarted_app.get_session("session-1")
            self.assertIsNotNone(session_detail)
            self.assertEqual(len(session_detail["messages"]), 2)

            # Delete session
            self.assertTrue(restarted_app.delete_session("session-1"))
            self.assertEqual(len(restarted_app.list_sessions()), 0)

    def test_webapp_session_rest_endpoints(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "web_sessions.sqlite3"
            store = SessionStore(database_path=db_path)
            session = store.create({"title": "Test Chat"}, session_id="chat-100")
            store.append_message("chat-100", "user", "Message 1")
            store.append_message("chat-100", "assistant", "Answer 1")

            registry = CapabilityRegistry()
            router = FakeRouter(
                RouteDecision("req-1", "routed", "chat", "respond", "conversation", "Chat intent")
            )
            app = Orchestrator(registry, router, sessions=store)

            server = _Server(("127.0.0.1", 0), app)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_port}"

            try:
                # 1. GET /api/sessions
                with urlopen(base_url + "/api/sessions", timeout=2) as resp:
                    self.assertEqual(resp.status, 200)
                    data = json.loads(resp.read().decode("utf-8"))
                    self.assertEqual(data["status"], "success")
                    self.assertEqual(len(data["sessions"]), 1)
                    self.assertEqual(data["sessions"][0]["session_id"], "chat-100")

                # 2. GET /api/sessions/chat-100
                with urlopen(base_url + "/api/sessions/chat-100", timeout=2) as resp:
                    self.assertEqual(resp.status, 200)
                    data = json.loads(resp.read().decode("utf-8"))
                    self.assertEqual(data["status"], "success")
                    self.assertEqual(len(data["session"]["messages"]), 2)

                # 3. GET /api/sessions/non-existent returns 404
                with self.assertRaises(HTTPError) as ctx:
                    urlopen(base_url + "/api/sessions/missing-id", timeout=2)
                self.assertEqual(ctx.exception.code, 404)

                # 4. POST /api/sessions/new
                req_new = Request(
                    base_url + "/api/sessions/new",
                    data=json.dumps({"session_id": "chat-200", "metadata": {"title": "Second"}}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(req_new, timeout=2) as resp:
                    self.assertEqual(resp.status, 200)
                    data = json.loads(resp.read().decode("utf-8"))
                    self.assertEqual(data["session_id"], "chat-200")

                # 5. DELETE /api/sessions/chat-200
                req_del = Request(base_url + "/api/sessions/chat-200", method="DELETE")
                with urlopen(req_del, timeout=2) as resp:
                    self.assertEqual(resp.status, 200)
                    data = json.loads(resp.read().decode("utf-8"))
                    self.assertTrue(data["deleted"])

                # Verify chat-200 is gone
                with self.assertRaises(HTTPError) as ctx:
                    urlopen(base_url + "/api/sessions/chat-200", timeout=2)
                self.assertEqual(ctx.exception.code, 404)

            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
