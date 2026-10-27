import unittest
from tara_app.openai_model_profiles import LocalModelProfile, default_local_profiles, profile_available

class LocalModelProfileTests(unittest.TestCase):
    def test_default_is_metadata_only_and_disabled(self):
        profile = default_local_profiles()[0]
        self.assertEqual(profile.model_id, "gpt-oss")
        self.assertFalse(profile.enabled)

    def test_runtime_presence_does_not_claim_weights_installed(self):
        profile = default_local_profiles()[0]
        self.assertTrue(profile_available(profile, {"ollama"}))
        self.assertFalse(profile_available(profile, set()))

    def test_rejects_invalid_limits(self):
        with self.assertRaises(ValueError):
            LocalModelProfile("gpt-oss", "ollama", context_tokens=0)

if __name__ == "__main__": unittest.main()
