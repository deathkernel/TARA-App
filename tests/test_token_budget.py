from __future__ import annotations

import unittest

from tara_chat.token_budget import (
    ContextBudgetError,
    ContextSection,
    estimate_tokens,
    pack_context,
)


class TokenBudgetTests(unittest.TestCase):
    def test_estimator_handles_empty_ascii_and_unicode(self):
        self.assertEqual(estimate_tokens(""), 0)
        self.assertGreater(estimate_tokens("hello world"), 0)
        self.assertGreater(estimate_tokens("नमस्ते"), 0)

    def test_required_sections_are_preserved_and_optional_sections_trimmed(self):
        plan = pack_context(
            [
                ContextSection("request", "must keep", 100, required=True),
                ContextSection("old history", "x" * 300, 1),
            ],
            max_tokens=20,
            estimator=lambda value: len(value),
        )
        self.assertIn("must keep", plan.text)
        self.assertEqual(plan.omitted_sections, ("old history",))

    def test_required_context_is_never_silently_truncated(self):
        with self.assertRaises(ContextBudgetError):
            pack_context(
                [ContextSection("request", "too long", 10, required=True)],
                max_tokens=2,
                estimator=len,
            )

    def test_output_reservation_is_applied_before_context(self):
        with self.assertRaises(ContextBudgetError):
            pack_context(
                [ContextSection("request", "x", 10, required=True)],
                max_tokens=10,
                reserve_tokens=10,
                estimator=len,
            )

    def test_duplicate_section_names_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            pack_context(
                [
                    ContextSection("same", "a", 1),
                    ContextSection("same", "b", 1),
                ],
                max_tokens=100,
            )


if __name__ == "__main__":
    unittest.main()
