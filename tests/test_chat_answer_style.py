import unittest

from tara_chat.brain import DEFAULT_SYSTEM_PROMPT


class ChatAnswerStyleTests(unittest.TestCase):
    def test_prompt_prioritizes_direct_and_structured_answers(self):
        self.assertIn("direct answer or takeaway first", DEFAULT_SYSTEM_PROMPT)
        self.assertIn("readable Markdown", DEFAULT_SYSTEM_PROMPT)
        self.assertIn("language-labelled fenced blocks", DEFAULT_SYSTEM_PROMPT)
        self.assertIn("Keep simple answers short", DEFAULT_SYSTEM_PROMPT)
        self.assertIn("repeated conclusions", DEFAULT_SYSTEM_PROMPT)

    def test_prompt_adapts_structure_to_task_type(self):
        for phrase in (
            "For how-to and troubleshooting requests",
            "For code requests",
            "For comparisons",
            "For study notes",
            "For plans",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, DEFAULT_SYSTEM_PROMPT)

    def test_prompt_requires_verified_action_status_and_uncertainty(self):
        self.assertIn("unless verified", DEFAULT_SYSTEM_PROMPT)
        self.assertIn("distinguish verified facts from", DEFAULT_SYSTEM_PROMPT)
        self.assertIn("completed, ", DEFAULT_SYSTEM_PROMPT)
        self.assertIn("not-yet-performed actions", DEFAULT_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
