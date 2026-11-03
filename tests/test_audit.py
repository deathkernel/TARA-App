"""Unit tests for redacted JSONL audit events."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tara_app.audit import JsonlAuditLog  # noqa: E402


class AuditLogTests(unittest.TestCase):
    def test_appends_parseable_records_and_redacts_sensitive_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "logs" / "audit.jsonl"
            audit = JsonlAuditLog(path)
            audit.record("request", {
                "request_id": "abc",
                "api_key": "do-not-write",
                "messages": [{"role": "user", "content": "private text"}],
                "nested": {"password": "hidden", "count": 2},
            })
            record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(record["event_type"], "request")
            self.assertEqual(record["fields"]["api_key"], "[REDACTED]")
            self.assertEqual(record["fields"]["messages"], "[REDACTED]")
            self.assertEqual(record["fields"]["nested"]["password"], "[REDACTED]")
            self.assertEqual(record["fields"]["nested"]["count"], 2)
            self.assertNotIn("do-not-write", path.read_text(encoding="utf-8"))
            self.assertNotIn("private text", path.read_text(encoding="utf-8"))

    def test_each_record_is_appended(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "audit.jsonl"
            audit = JsonlAuditLog(path)
            audit.record("first")
            audit.record("second")
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 2)

    def test_blank_event_name_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                JsonlAuditLog(Path(temp) / "audit.jsonl").record(" ")


if __name__ == "__main__":
    unittest.main()
