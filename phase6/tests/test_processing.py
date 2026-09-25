import tempfile
import unittest
from pathlib import Path

from phase1.pipeline import Pipeline, ProcessRecordStore
from phase6.processing import ProcessingRequest, process_request


class TestProcessingRequest(unittest.TestCase):
    def test_requires_an_api_key(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "source.png"
            image.write_bytes(b"image")
            request = ProcessingRequest(image, Path(directory) / "out", "", "https://example.test", "model")
            with self.assertRaisesRegex(ValueError, "API Key"):
                request.validate()

    def test_manual_processing_preserves_source_on_failure(self):
        captured = {}

        class FakePipeline:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def process_image(self, image_path):
                return "failed"

        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "source.png"
            image.write_bytes(b"image")
            request = ProcessingRequest(image, Path(directory) / "out", "key", "https://example.test", "model")
            result = process_request(request, provider_factory=lambda *args: object(), pipeline_factory=FakePipeline)
            self.assertEqual(result.status, "failed")
            self.assertFalse(captured["move_failed"])
            self.assertTrue(image.exists())

    def test_existing_pipeline_keeps_move_on_failure_as_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = Pipeline(
                provider=object(),
                input_dir=root,
                output_dir=root / "out",
                failed_dir=root / "failed",
                store=ProcessRecordStore(root / "processed.json"),
            )
            self.assertTrue(pipeline.move_failed)


if __name__ == "__main__":
    unittest.main()
