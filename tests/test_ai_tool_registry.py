"""Policy regression tests for the AI tool registry."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate_ai_tool_registry import validate_registry  # noqa: E402


class ToolRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "config" / "ai_tool_registry.json").read_text(encoding="utf-8"))

    def test_registry_has_thirty_valid_entries(self):
        self.assertEqual(validate_registry(self.data), [])
        self.assertEqual(len(self.data["tools"]), 30)

    def test_ids_are_unique(self):
        ids = [item["id"] for item in self.data["tools"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_tools_are_disabled(self):
        self.assertTrue(all(item["enabled"] is False for item in self.data["tools"]))

    def test_execution_agents_are_blocked(self):
        items = {item["id"]: item for item in self.data["tools"]}
        for tool_id in ("openhands", "open-interpreter"):
            self.assertEqual(items[tool_id]["status"], "blocked_pending_sandbox")
            self.assertIs(items[tool_id]["requires_hardened_sandbox"], True)
            self.assertIs(items[tool_id]["shell_access"], False)

    def test_policy_rejects_enabling_a_tool(self):
        changed = json.loads(json.dumps(self.data))
        changed["tools"][0]["enabled"] = True
        self.assertTrue(any("must remain disabled" in error for error in validate_registry(changed)))


if __name__ == "__main__":
    unittest.main()
