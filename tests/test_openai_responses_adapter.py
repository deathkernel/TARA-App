import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from tara_app.openai_responses_adapter import OpenAIResponsesAdapter, OpenAISDKUnavailable

class OpenAIResponsesAdapterTests(unittest.TestCase):
    def test_disabled_by_default_and_does_not_call_client(self):
        client = Mock()
        adapter = OpenAIResponsesAdapter(client=client)
        with self.assertRaises(OpenAISDKUnavailable):
            adapter.complete(model="model", input_text="hello")
        client.responses.create.assert_not_called()

    def test_calls_injected_client_only_when_enabled(self):
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(output_text="hello back")
        adapter = OpenAIResponsesAdapter(enabled=True, client=client)
        self.assertEqual(adapter.complete(model="example-model", input_text="hello"), "hello back")
        client.responses.create.assert_called_once_with(model="example-model", input="hello", max_output_tokens=1024)

    def test_rejects_invalid_limits_before_call(self):
        client = Mock()
        adapter = OpenAIResponsesAdapter(enabled=True, client=client)
        with self.assertRaises(ValueError):
            adapter.complete(model="model", input_text="hello", max_output_tokens=0)
        client.responses.create.assert_not_called()

if __name__ == "__main__":
    unittest.main()
