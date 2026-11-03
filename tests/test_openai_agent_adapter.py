import unittest
from tara_app.openai_agent_adapter import AgentAdapterError, GuardedAgentAdapter

class AgentAdapterTests(unittest.TestCase):
    def test_disabled_by_default(self):
        adapter = GuardedAgentAdapter(lambda prompt, context: prompt)
        with self.assertRaises(AgentAdapterError): adapter.run("hello")

    def test_denies_unlisted_tools(self):
        adapter = GuardedAgentAdapter(lambda prompt, context: prompt, allowed_tools=frozenset({"lookup"}), enabled=True)
        with self.assertRaises(AgentAdapterError): adapter.run("hello", requested_tools=("shell",))

    def test_runs_injected_runner_with_allowed_tools(self):
        adapter = GuardedAgentAdapter(lambda prompt, context: (prompt, context["allowed_tools"]), allowed_tools=frozenset({"lookup"}), enabled=True)
        self.assertEqual(adapter.run("hello", requested_tools=("lookup",)), ("hello", ("lookup",)))

if __name__ == "__main__": unittest.main()
