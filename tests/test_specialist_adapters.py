"""Tests for injected specialist adapter boundaries."""
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tara_app.adapters.chat import TaraChatAdapter
from tara_app.adapters.code import TaraCodeAdapter
from tara_app.contracts import SpecialistRequest

class AdapterTests(unittest.TestCase):
    def test_chat_adapter_validates_and_returns_text(self):
        adapter = TaraChatAdapter(lambda session, messages: "hello " + messages[-1]["content"])
        result = adapter.handle(SpecialistRequest("r1", "chat.reply", {
            "session_id": "s1", "messages": [{"role": "user", "content": "there"}]
        }))
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.output["reply"], "hello there")

    def test_chat_adapter_rejects_wrong_capability(self):
        adapter = TaraChatAdapter(lambda session, messages: "unused")
        result = adapter.handle(SpecialistRequest("r2", "chat.delete", {
            "session_id": "s1", "messages": [{"role": "user", "content": "x"}]
        }))
        self.assertEqual(result.status, "unsupported_capability")

    def test_code_adapter_only_returns_proposals(self):
        adapter = TaraCodeAdapter(lambda payload: {
            "summary": "reviewed", "proposed_changes": [{"path": "src/a.py", "diff": "+x"}],
            "warnings": ["human review required"]
        })
        result = adapter.handle(SpecialistRequest("r3", "code.review", {"task": "inspect"}))
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.output, {"summary": "reviewed"})
        self.assertEqual(len(result.proposed_changes), 1)
        self.assertEqual(result.warnings, ("human review required",))

    def test_code_adapter_rejects_invalid_proposal_shape(self):
        adapter = TaraCodeAdapter(lambda payload: {"proposed_changes": "apply now"})
        self.assertEqual(adapter.handle(SpecialistRequest("r4", "code.plan", {})).status, "invalid_response")

if __name__ == "__main__":
    unittest.main()
