import unittest
from unittest.mock import patch
from tara_app.optional_tokenizer import count_tokens

class OptionalTokenizerTests(unittest.TestCase):
    def test_rejects_non_string_input(self):
        with self.assertRaises(ValueError): count_tokens(None)

    def test_counts_using_selected_encoding(self):
        class FakeEncoding:
            def encode(self, text): return [1, 2, 3]
        class FakeTiktoken:
            @staticmethod
            def get_encoding(name):
                if name != "o200k_base": raise KeyError(name)
                return FakeEncoding()
        with patch.dict("sys.modules", {"tiktoken": FakeTiktoken}):
            self.assertEqual(count_tokens("hello"), 3)

    def test_unknown_encoding_is_reported(self):
        class FakeTiktoken:
            @staticmethod
            def get_encoding(name): raise KeyError(name)
        with patch.dict("sys.modules", {"tiktoken": FakeTiktoken}):
            with self.assertRaises(ValueError): count_tokens("hello", encoding_name="bad")

if __name__ == "__main__": unittest.main()
