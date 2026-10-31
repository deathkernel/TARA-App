from __future__ import annotations
import unittest
from tara_app.builtin_router import BuiltinRouter

class StudyRoutingTests(unittest.TestCase):
    def route(self, question, capabilities):
        return BuiltinRouter().route({"request_id":"study-test","question":question,"available_capabilities":capabilities,"attachments":[]})
    def test_quiz_request_routes_to_study(self):
        result=self.route("Make a quiz from my notes",["chat.respond","study.create"])
        self.assertEqual((result.status,result.module,result.action),("routed","study","create"))
    def test_study_intent_overrides_generic_text_attachment_route(self):
        result=BuiltinRouter().route({"request_id":"study-attachment","question":"Create a quiz from the attached notes","available_capabilities":["chat.respond","code.plan","study.create"],"attachments":[{"media_type":"text/plain","name":"notes.txt"}]})
        self.assertEqual((result.module,result.action),("study","create"))
    def test_study_plan_routes_to_study(self):
        result=self.route("Create a 7 day study plan for biology",["chat.respond","study.create"])
        self.assertEqual((result.module,result.action),("study","create"))
    def test_study_request_fails_closed_when_not_enabled(self):
        result=self.route("Make flashcards from this chapter",["chat.respond"])
        self.assertEqual(result.status,"unavailable")
        self.assertEqual(result.reason_code,"capability_unavailable")
    def test_weather_routes_to_public_weather(self):
        result=self.route("What's the weather like in Pune today?",["chat.respond","weather.forecast"])
        self.assertEqual((result.status,result.module,result.action),("routed","weather","forecast"))
    def test_free_model_catalog_routes_to_model_hub(self):
        result=self.route("List all available free models",["chat.respond","models.catalog"])
        self.assertEqual((result.module,result.action),("models","catalog"))
    def test_explicit_gemini_selection_routes_to_model_hub(self):
        result=self.route("Use Gemini: explain photosynthesis",["chat.respond","models.generate"])
        self.assertEqual((result.module,result.action),("models","generate"))
    def test_bharatcode_qwen_selection_routes_to_model_hub(self):
        result=self.route("Use qwen-3.8-27b: explain this topic",["chat.respond","models.generate"])
        self.assertEqual((result.module,result.action),("models","generate"))
    def test_openai_gpt_oss_selection_routes_to_model_hub(self):
        result=self.route("Use OpenAI gpt-oss:20b: explain this topic",["chat.respond","models.generate"])
        self.assertEqual((result.module,result.action),("models","generate"))
    def test_rain_question_routes_to_weather(self):
        result=self.route("Will it rain in Pune?",["chat.respond","weather.forecast"])
        self.assertEqual((result.module,result.action),("weather","forecast"))
    def test_normal_chat_is_not_routed_to_study(self):
        result=self.route("Hello, how are you?",["chat.respond","study.create"])
        self.assertEqual((result.module,result.action),("chat","respond"))

if __name__=="__main__": unittest.main()
