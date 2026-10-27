import unittest
from tara_app.optional_guardrails import OptionalGuardrail

class GuardrailTests(unittest.TestCase):
    def test_missing_evaluator_fails_closed(self):
        self.assertFalse(OptionalGuardrail().check("hello").allowed)

    def test_false_result_blocks(self):
        self.assertFalse(OptionalGuardrail(lambda text: False).check("hello").allowed)

    def test_exception_fails_closed(self):
        def fail(text): raise RuntimeError("sensitive details")
        result = OptionalGuardrail(fail).check("hello")
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "evaluation_failed")

if __name__ == "__main__": unittest.main()
