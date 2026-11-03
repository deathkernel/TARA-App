import unittest

from tara_chat.brain import DEFAULT_MAX_NEW_TOKENS, DEFAULT_SYSTEM_PROMPT


class ChatAnswerStyleTests(unittest.TestCase):
    def test_prompt_prioritizes_direct_and_structured_answers(self):
        self.assertIn("direct answer or takeaway", DEFAULT_SYSTEM_PROMPT)
        self.assertIn("readable Markdown", DEFAULT_SYSTEM_PROMPT)
        self.assertIn("language-labelled", DEFAULT_SYSTEM_PROMPT)
        self.assertIn("simple question gets a short reply", DEFAULT_SYSTEM_PROMPT)
        self.assertIn("repeated conclusions", DEFAULT_SYSTEM_PROMPT)

    def test_prompt_adapts_structure_to_task_type(self):
        for phrase in (
            "How-to / troubleshooting",
            "Code:",
            "Comparisons:",
            "Study:",
            "Plans:",
            "Research / factual claims",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, DEFAULT_SYSTEM_PROMPT)

    def test_prompt_requires_verified_action_status_and_uncertainty(self):
        self.assertIn("unless that action was actually verified", DEFAULT_SYSTEM_PROMPT)
        self.assertIn("known vs uncertain", DEFAULT_SYSTEM_PROMPT)
        self.assertIn("never fabricate paper titles", DEFAULT_SYSTEM_PROMPT)

    def test_default_token_budget_allows_full_answers(self):
        # 128 truncated most useful replies; polished answers need headroom.
        self.assertGreaterEqual(DEFAULT_MAX_NEW_TOKENS, 1024)
        self.assertLessEqual(DEFAULT_MAX_NEW_TOKENS, 4096)


if __name__ == "__main__":
    unittest.main()
