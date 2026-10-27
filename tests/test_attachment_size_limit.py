from __future__ import annotations

import base64
import unittest

from tara_app.orchestrator import TARAOrchestrator


def attachment(size: int, name: str = "document.txt") -> dict[str, str]:
    encoded = base64.b64encode(b"x" * size).decode("ascii")
    return {
        "name": name,
        "media_type": "text/plain",
        "content_base64": encoded,
    }


class AttachmentSizeLimitTests(unittest.TestCase):
    def test_attachment_at_10_mb_is_accepted(self):
        result = TARAOrchestrator._validate_attachments([attachment(10_000_000)])
        self.assertEqual(len(base64.b64decode(result[0]["content_base64"])), 10_000_000)

    def test_single_attachment_over_10_mb_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "10 MB"):
            TARAOrchestrator._validate_attachments([attachment(10_000_001)])

    def test_combined_attachments_over_10_mb_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "10 MB per-message"):
            TARAOrchestrator._validate_attachments([
                attachment(6_000_000, "first.txt"),
                attachment(4_000_001, "second.txt"),
            ])


if __name__ == "__main__":
    unittest.main()
