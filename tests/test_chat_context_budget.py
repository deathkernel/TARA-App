from __future__ import annotations

import unittest

from tara_chat.brain import TARABrain


class _Memory:
    def retrieve(self, query, limit=5):
        return [
            {"key": "project", "value": "TARA is local-first", "score": 1.0},
            {"key": "unrelated", "value": "x" * 5000, "score": 0.01},
        ][:limit]

    def remember(self, key, value, importance=1.0):
        return value

    def save(self):
        return None


class _Provider:
    def __init__(self):
        self.calls = []
        self.last_usage = {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}

    def complete(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return "A useful answer."


class ChatContextBudgetTests(unittest.TestCase):
    def test_context_budget_keeps_current_request_and_trims_old_history(self):
        provider = _Provider()
        brain = TARABrain(
            memory=_Memory(),
            llm_provider=provider,
            system_prompt="system",
            max_input_tokens=300,
            memory_token_budget=50,
            recent_history_turns=4,
            token_estimator=lambda value: len(value),
        )
        brain.conversation_history = [
            ("User", "old context " * 50),
            ("TARA", "old answer " * 50),
            ("User", "recent question"),
            ("TARA", "recent answer"),
        ]
        result = brain.respond("current request", max_new_tokens=20)
        sent = provider.calls[0][0]
        self.assertIn("current request", sent)
        self.assertNotIn("old context", sent)
        self.assertEqual(result.provider_usage["total_tokens"], 30)
        self.assertIn("Recent conversation", result.omitted_context)

    def test_context_budget_refuses_to_drop_the_current_request(self):
        provider = _Provider()
        brain = TARABrain(
            memory=_Memory(),
            llm_provider=provider,
            system_prompt="system",
            max_input_tokens=20,
            token_estimator=lambda value: len(value),
        )
        with self.assertRaisesRegex(ValueError, "exceed"):
            brain.respond("x" * 100, max_new_tokens=10)
        self.assertEqual(provider.calls, [])

    def test_provider_usage_is_optional(self):
        provider = _Provider()
        provider.last_usage = None
        brain = TARABrain(memory=_Memory(), llm_provider=provider, system_prompt="system")
        result = brain.respond("hello")
        self.assertIsNone(result.provider_usage)


if __name__ == "__main__":
    unittest.main()
