from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tara_app.security_vault import SecurityVault


class SecurityVaultTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.vault_path = Path(self.temp_dir.name) / "vault.bin"
        self.vault = SecurityVault(self.vault_path)

    def test_store_and_retrieve_secret(self):
        self.vault.set_secret("TEST_KEY", "super_secret_value_12345")
        retrieved = self.vault.get_secret("TEST_KEY")
        self.assertEqual(retrieved, "super_secret_value_12345")

    def test_persistence_across_instances(self):
        self.vault.set_secret("API_KEY", "my_token")
        new_vault = SecurityVault(self.vault_path)
        self.assertEqual(new_vault.get_secret("API_KEY"), "my_token")

    def test_masked_secrets_does_not_reveal_full_secret(self):
        self.vault.set_secret("API_KEY", "sk-1234567890abcdef")
        masked = self.vault.get_masked_secrets()
        self.assertIn("API_KEY", masked)
        self.assertNotIn("1234567890", masked["API_KEY"])
        self.assertTrue(masked["API_KEY"].startswith("sk-"))

    def test_delete_secret(self):
        self.vault.set_secret("TO_DELETE", "val")
        self.assertTrue(self.vault.delete_secret("TO_DELETE"))
        self.assertIsNone(self.vault.get_secret("TO_DELETE"))
        self.assertFalse(self.vault.delete_secret("TO_DELETE"))

    def test_rejects_invalid_keys(self):
        with self.assertRaises(ValueError):
            self.vault.set_secret("", "val")
        with self.assertRaises(ValueError):
            self.vault.set_secret("k" * 200, "val")


if __name__ == "__main__":
    unittest.main()
