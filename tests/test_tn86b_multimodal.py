"""Tests for TN-86B multimodal normalization and cognitive bridging."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tara_app.cognition import CognitiveCoordinator, CognitiveRequest, ContextBuilder, DecisionStatus
from tara_app.memory import MemoryEngine, SQLiteMemoryRepository
from tara_app.multimodal import Modality, MultimodalCognitiveBridge, MultimodalInputPipeline, MultimodalObservation


class MultimodalModelTests(unittest.TestCase):
    def test_observation_rejects_empty_or_oversized_content(self):
        with self.assertRaises(ValueError):
            MultimodalObservation("id", Modality.TEXT, " ", "test")
        with self.assertRaises(ValueError):
            MultimodalObservation("id", Modality.TEXT, "x" * 20_001, "test")

    def test_observation_rejects_invalid_confidence_and_attributes(self):
        with self.assertRaises(ValueError):
            MultimodalObservation("id", Modality.TEXT, "hello", "test", confidence=float("nan"))
        with self.assertRaises(ValueError):
            MultimodalObservation("id", Modality.TEXT, "hello", "test", attributes=(("Bad-Key", "x"),))


class MultimodalPipelineTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = MultimodalInputPipeline(clock=lambda: 123.0)

    def test_local_voice_result_becomes_transcript_observation(self):
        item = self.pipeline.from_voice_result({
            "status": "success",
            "data": {"text": "  turn left  ", "local": True, "language_code": "en", "model": "base"},
        })
        self.assertEqual(item.modality, Modality.VOICE_TRANSCRIPT)
        self.assertEqual(item.content, "turn left")
        self.assertEqual(item.created_at, 123.0)
        self.assertIn(("language_code", "en"), item.attributes)

    def test_voice_result_rejects_non_local_source(self):
        with self.assertRaises(ValueError):
            self.pipeline.from_voice_result({"status": "success", "data": {"text": "hello", "local": False}})

    def test_vision_result_records_omniroute_boundary(self):
        item = self.pipeline.from_vision_result({
            "status": "success",
            "data": {
                "text": "A red vehicle is visible.",
                "provider": "omniroute",
                "model": "vision-route",
                "images_sent_to_remote": True,
            },
        })
        self.assertEqual(item.modality, Modality.IMAGE_ANALYSIS)
        self.assertIn(("media_routed", "through_omniroute"), item.attributes)

    def test_vision_result_rejects_unconfigured_provider(self):
        with self.assertRaises(ValueError):
            self.pipeline.from_vision_result({"status": "success", "data": {"text": "description", "provider": "other"}})

    def test_failed_specialist_results_are_not_ingested(self):
        with self.assertRaises(ValueError):
            self.pipeline.from_voice_result({"status": "unavailable", "data": {}})

    def test_batch_rejects_duplicate_ids_and_excessive_size(self):
        item = self.pipeline.from_text("hello")
        with self.assertRaises(ValueError):
            self.pipeline.to_context_items((item, item))
        large = tuple(
            MultimodalObservation(f"large-{index}", Modality.TEXT, "x" * 20_000, "text")
            for index in range(5)
        )
        with self.assertRaises(ValueError):
            self.pipeline.to_context_items(large)

    def test_context_conversion_keeps_source_and_confidence(self):
        item = self.pipeline.from_text("current screen says ready")
        context = self.pipeline.to_context_items((item,))
        self.assertEqual(context[0].source, "multimodal:text")
        self.assertEqual(context[0].features.confidence, 1.0)


class MultimodalBridgeTests(unittest.TestCase):
    def test_bridge_passes_observations_to_cognition_without_fabricating_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteMemoryRepository(
                Path(directory) / "memory.sqlite3",
                authorize_write=lambda: True,
            )
            memory = MemoryEngine(repository)
            coordinator = CognitiveCoordinator(ContextBuilder(memory))
            pipeline = MultimodalInputPipeline(clock=lambda: 100.0)
            bridge = MultimodalCognitiveBridge(coordinator, pipeline)
            observation = pipeline.from_text("The displayed status is ready.")
            decision, trace = bridge.process(
                CognitiveRequest("multimodal-1", "What does the display say?"),
                (observation,),
            )
            self.assertEqual(decision.status, DecisionStatus.ABSTAINED)
            self.assertIn(observation.observation_id, trace.context_item_ids)
            self.assertEqual(memory.recall("display"), ())


if __name__ == "__main__":
    unittest.main()
