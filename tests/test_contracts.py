"""Tests for shared provider and specialist contract shapes."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tara_app.contracts import (  # noqa: E402
    SPECIALIST_CONTRACT_VERSION, SpecialistRequest, SpecialistResult,
)


class SpecialistContractTests(unittest.TestCase):
    def test_request_and_result_share_versioned_boundary(self):
        request = SpecialistRequest("req-1", "chat.reply", {"text": "hello"})
        result = SpecialistResult("req-1", "ok", output={"reply": "hi"})
        self.assertEqual(request.contract_version, SPECIALIST_CONTRACT_VERSION)
        self.assertEqual(result.contract_version, SPECIALIST_CONTRACT_VERSION)
        self.assertEqual(result.request_id, request.request_id)

    def test_proposed_changes_are_separate_from_output(self):
        result = SpecialistResult(
            "req-2", "proposal",
            proposed_changes=({"path": "src/example.py", "diff": "@@ -1 +1 @@"},),
            warnings=("Human review required",),
        )
        self.assertEqual(result.status, "proposal")
        self.assertEqual(len(result.proposed_changes), 1)
        self.assertEqual(result.warnings, ("Human review required",))


if __name__ == "__main__":
    unittest.main()
