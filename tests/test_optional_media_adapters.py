import unittest
from tara_app.optional_media_adapters import LocalTranscriptionAdapter, ImageTextSimilarityAdapter, MediaAdapterUnavailable

class MediaAdapterTests(unittest.TestCase):
    def test_transcription_is_unavailable_without_backend(self):
        with self.assertRaises(MediaAdapterUnavailable): LocalTranscriptionAdapter().run(b"audio")

    def test_transcription_enforces_size_and_result_type(self):
        self.assertEqual(LocalTranscriptionAdapter(lambda data: "ok").run(b"audio"), "ok")
        with self.assertRaises(ValueError): LocalTranscriptionAdapter(max_bytes=2, transcribe=lambda data: "ok").run(b"audio")

    def test_similarity_requires_backend(self):
        with self.assertRaises(MediaAdapterUnavailable): ImageTextSimilarityAdapter().run(object(), "cat")
        self.assertEqual(ImageTextSimilarityAdapter(lambda image, text: 0.5).run(object(), "cat"), 0.5)

if __name__ == "__main__": unittest.main()
