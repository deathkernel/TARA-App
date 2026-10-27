"""Tests for the model catalogue."""
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tara_app.contracts import ModelInfo
from tara_app.model_catalogue import ModelCatalogue, ModelCatalogueError, ModelQuery

class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.models = [
            ModelInfo("ollama", "llama3:latest", family="llama", quantization_level="Q4_K_M"),
            ModelInfo("ollama", "mistral:latest", family="mistral", quantization_level="Q5_K_M"),
            ModelInfo("localai", "llama3", family="llama"),
        ]
        self.catalogue = ModelCatalogue(self.models)

    def test_filters_by_provider_family_quantization_and_text(self):
        self.assertEqual(len(self.catalogue.list(ModelQuery(provider_id="ollama"))), 2)
        self.assertEqual(len(self.catalogue.list(ModelQuery(family="llama"))), 2)
        self.assertEqual(len(self.catalogue.list(ModelQuery(quantization_level="Q4_K_M"))), 1)
        self.assertEqual(len(self.catalogue.list(ModelQuery(text="MISTRAL"))), 1)

    def test_get_exact_model_and_missing_model(self):
        self.assertEqual(self.catalogue.get("ollama", "mistral:latest").family, "mistral")
        with self.assertRaises(ModelCatalogueError):
            self.catalogue.get("ollama", "missing")

    def test_duplicate_models_rejected(self):
        with self.assertRaises(ModelCatalogueError):
            ModelCatalogue([self.models[0], self.models[0]])

if __name__ == "__main__":
    unittest.main()
