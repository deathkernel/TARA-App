from __future__ import annotations
import base64
import unittest
from tara_study.__main__ import handle_request
SOURCE = "Photosynthesis is the process by which green plants convert light energy into chemical energy. Chlorophyll absorbs light in the leaves. Carbon dioxide and water are used to produce glucose and oxygen."
def request(question: str, **inputs):
    return {"schema_version":"1.0","request_id":"test-1","session_id":"session-1","module":"study","action":"create","inputs":{"question":question,**inputs}}
class StudyModuleTests(unittest.TestCase):
    def test_health_is_offline(self):
        result=handle_request({"schema_version":"1.0","request_id":"h","module":"study","action":"health"})
        self.assertEqual(result["status"],"success"); self.assertTrue(result["data"]["offline"])
    def test_notes_are_source_grounded(self):
        result=handle_request(request("make notes",source_text=SOURCE))
        self.assertEqual(result["status"],"success"); self.assertTrue(result["data"]["source_grounded"]); self.assertIn("Chlorophyll absorbs light",result["data"]["text"])
    def test_quiz_answers_are_source_exact(self):
        result=handle_request(request("make a quiz",source_text=SOURCE,count=2))
        self.assertEqual(result["status"],"success"); self.assertEqual(result["data"]["kind"],"quiz"); self.assertEqual(len(result["data"]["items"]),2); self.assertIn(result["data"]["items"][0]["answer"],SOURCE)
    def test_flashcards_accept_text_attachment(self):
        encoded=base64.b64encode(SOURCE.encode()).decode()
        result=handle_request(request("create flashcards",attachments=[{"name":"notes.txt","media_type":"text/plain","content_base64":encoded}],count=1))
        self.assertEqual(result["status"],"success"); self.assertEqual(result["data"]["kind"],"flashcards"); self.assertEqual(result["data"]["items"][0]["source_line"],1)
    def test_plan_is_bounded(self):
        result=handle_request(request("make a 5 day study plan for biology"))
        self.assertEqual(result["status"],"success"); self.assertEqual(result["data"]["text"].count("## Day "),5); self.assertIn("Study Plan: biology",result["data"]["text"])
    def test_notes_require_source(self): self.assertEqual(handle_request(request("make notes"))["status"],"invalid_request")
    def test_count_is_bounded(self): self.assertEqual(handle_request(request("make quiz",source_text=SOURCE,count=1000))["status"],"invalid_request")
    def test_unknown_fields_rejected(self): self.assertEqual(handle_request({"schema_version":"1.0","request_id":"x","module":"study","action":"health","oops":True})["status"],"invalid_request")
if __name__=="__main__": unittest.main()
