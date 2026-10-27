import unittest
from tara_chat.brain import DEFAULT_SYSTEM_PROMPT

class ChatAnswerStyleTests(unittest.TestCase):
    def test_prompt_prioritizes_direct_and_structured_answers(self):
        self.assertIn("Start with the direct answer",DEFAULT_SYSTEM_PROMPT)
        self.assertIn("concise",DEFAULT_SYSTEM_PROMPT)
        self.assertIn("repeated conclusions",DEFAULT_SYSTEM_PROMPT)
    def test_prompt_requires_honesty_about_actions(self):
        self.assertIn("unless verified",DEFAULT_SYSTEM_PROMPT)
if __name__=="__main__": unittest.main()
