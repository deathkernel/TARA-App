import unittest
from unittest.mock import patch
from tara_models.__main__ import handle_request, GEMINI_FREE_TEXT_MODELS

class ModelHubTests(unittest.TestCase):
    def test_adapter_health_does_not_require_api_key(self):
        result=handle_request({"schema_version":"1.0","request_id":"h","module":"models","action":"health"})
        self.assertEqual(result["status"],"success"); self.assertTrue(result["data"]["healthy"])
    def test_catalog_works_without_api_key(self):
        result=handle_request({"schema_version":"1.0","request_id":"x","module":"models","action":"catalog","inputs":{}})
        self.assertEqual(result["status"],"success"); self.assertIn("gpt-oss:20b",result["data"]["text"]); self.assertIn("GEMINI_API_KEY",result["data"]["text"])
    def test_catalog_lists_free_candidates_without_key(self):
        result=handle_request({"schema_version":"1.0","request_id":"x","module":"models","action":"catalog","inputs":{}})
        self.assertIn("gemini-3.1-flash-lite",result["data"]["text"])
        self.assertIn("gemini-2.5-flash-lite",result["data"]["text"])
    def test_unknown_model_rejected(self):
        result=handle_request({"schema_version":"1.0","request_id":"x","module":"models","action":"generate","inputs":{"question":"hello","model":"gemini-paid-model"}})
        self.assertEqual(result["status"],"unavailable")
    def test_no_paid_openai_api_path(self): self.assertTrue(all(item["provider"]=="ollama" for item in __import__("tara_models.__main__",fromlist=["OPENAI_OPEN_WEIGHT_MODELS"]).OPENAI_OPEN_WEIGHT_MODELS))
    def test_gemini_free_model_allowlist_is_explicit(self): self.assertIn("gemini-3.5-flash-lite",GEMINI_FREE_TEXT_MODELS)
    def test_invalid_request_rejected(self): self.assertEqual(handle_request({"schema_version":"1.0","request_id":"x","module":"models","action":"generate","inputs":{"question":""}})["status"],"invalid_request")
if __name__=="__main__": unittest.main()
