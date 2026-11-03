from __future__ import annotations

import unittest

from tara_app.contracts import MAX_PAYLOAD_BYTES, ContractError, ModuleRequest


class PayloadSizeLimitTests(unittest.TestCase):
    def test_payload_limit_is_50_mb(self):
        self.assertEqual(MAX_PAYLOAD_BYTES, 50_000_000)

    def test_request_payload_larger_than_previous_1_mb_limit_is_accepted(self):
        request = ModuleRequest(
            request_id="large-attachment",
            session_id="test-session",
            module="vision",
            action="analyze",
            inputs={"attachment_data": "x" * 1_100_000},
        )
        self.assertGreater(len(str(request.to_payload())), 1_000_000)

    def test_request_payload_above_configured_limit_is_rejected(self):
        with self.assertRaises(ContractError):
            ModuleRequest(
                request_id="oversized-payload",
                session_id="test-session",
                module="vision",
                action="analyze",
                inputs={"attachment_data": "x" * MAX_PAYLOAD_BYTES},
            )


if __name__ == "__main__":
    unittest.main()
