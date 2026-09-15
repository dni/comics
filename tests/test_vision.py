import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from comics_importer.errors import VisionAPIError
from comics_importer.vision import (
    COMIC_METADATA_SCHEMA,
    CROP_SCHEMA,
    GRADE_SCHEMA,
    assess_grade,
    estimate_crop,
    identify_metadata,
)


class TestIdentifyMetadata(unittest.TestCase):
    def _thumb(self, tmpdir: str) -> Path:
        p = Path(tmpdir) / "thumb.jpg"
        p.write_bytes(b"fake-jpeg-bytes")
        return p

    def test_sends_correct_request_shape_and_parses_response(self):
        expected_metadata = {
            "series": "Goofy",
            "issue_number": "1",
            "year": 1990,
            "publisher": "Egmont",
            "language": "de",
            "condition_grade": "Very Fine",
            "numeric_grade": 8.0,
            "confidence": "high",
            "notes": None,
            "rotation_degrees": -3.5,
            "crop_left": 0.08,
            "crop_top": 0.05,
            "crop_width": 0.84,
            "crop_height": 0.9,
        }
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = json.dumps(expected_metadata)

        response = MagicMock()
        response.stop_reason = "end_turn"
        response.content = [text_block]

        client = MagicMock()
        client.messages.create.return_value = response

        with tempfile.TemporaryDirectory() as d:
            metadata, raw_json = identify_metadata(self._thumb(d), client, model="claude-opus-4-8")

        self.assertEqual(metadata, expected_metadata)
        self.assertEqual(json.loads(raw_json), expected_metadata)

        _, kwargs = client.messages.create.call_args
        self.assertEqual(kwargs["model"], "claude-opus-4-8")
        self.assertEqual(kwargs["output_config"]["format"]["schema"], COMIC_METADATA_SCHEMA)
        content = kwargs["messages"][0]["content"]
        self.assertEqual(content[0]["type"], "image")
        self.assertEqual(content[0]["source"]["media_type"], "image/jpeg")

    def test_refusal_raises_vision_api_error(self):
        response = MagicMock()
        response.stop_reason = "refusal"

        client = MagicMock()
        client.messages.create.return_value = response

        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(VisionAPIError):
                identify_metadata(self._thumb(d), client)

    def test_invalid_json_raises_vision_api_error(self):
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "not json"

        response = MagicMock()
        response.stop_reason = "end_turn"
        response.content = [text_block]

        client = MagicMock()
        client.messages.create.return_value = response

        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(VisionAPIError):
                identify_metadata(self._thumb(d), client)


class TestAssessGrade(unittest.TestCase):
    def _thumb(self, tmpdir: str) -> Path:
        p = Path(tmpdir) / "thumb.jpg"
        p.write_bytes(b"fake-jpeg-bytes")
        return p

    def test_sends_grading_schema_and_parses_response(self):
        expected = {
            "condition_grade": "Very Fine",
            "numeric_grade": 8.0,
            "grading_notes": "Sharp corners, minor spine tick.",
        }
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = json.dumps(expected)

        response = MagicMock()
        response.stop_reason = "end_turn"
        response.content = [text_block]

        client = MagicMock()
        client.messages.create.return_value = response

        with tempfile.TemporaryDirectory() as d:
            grade, raw_json = assess_grade(self._thumb(d), client, model="claude-opus-4-8")

        self.assertEqual(grade, expected)
        self.assertEqual(json.loads(raw_json), expected)

        _, kwargs = client.messages.create.call_args
        self.assertEqual(kwargs["model"], "claude-opus-4-8")
        # must use the dedicated grading schema, not the full identification one
        self.assertEqual(kwargs["output_config"]["format"]["schema"], GRADE_SCHEMA)
        self.assertNotEqual(GRADE_SCHEMA, COMIC_METADATA_SCHEMA)

    def test_refusal_raises_vision_api_error(self):
        response = MagicMock()
        response.stop_reason = "refusal"

        client = MagicMock()
        client.messages.create.return_value = response

        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(VisionAPIError):
                assess_grade(self._thumb(d), client)


class TestEstimateCrop(unittest.TestCase):
    def _thumb(self, tmpdir: str) -> Path:
        p = Path(tmpdir) / "thumb.jpg"
        p.write_bytes(b"fake-jpeg-bytes")
        return p

    def test_sends_crop_schema_and_parses_response(self):
        expected = {
            "rotation_degrees": -2.5,
            "crop_left": 0.06,
            "crop_top": 0.04,
            "crop_width": 0.88,
            "crop_height": 0.92,
        }
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = json.dumps(expected)

        response = MagicMock()
        response.stop_reason = "end_turn"
        response.content = [text_block]

        client = MagicMock()
        client.messages.create.return_value = response

        with tempfile.TemporaryDirectory() as d:
            crop, raw_json = estimate_crop(self._thumb(d), client, model="claude-opus-4-8")

        self.assertEqual(crop, expected)
        self.assertEqual(json.loads(raw_json), expected)

        _, kwargs = client.messages.create.call_args
        self.assertEqual(kwargs["model"], "claude-opus-4-8")
        # must use the dedicated crop-only schema, not the full identification one
        self.assertEqual(kwargs["output_config"]["format"]["schema"], CROP_SCHEMA)
        self.assertNotEqual(CROP_SCHEMA, COMIC_METADATA_SCHEMA)
        self.assertNotEqual(CROP_SCHEMA, GRADE_SCHEMA)

    def test_refusal_raises_vision_api_error(self):
        response = MagicMock()
        response.stop_reason = "refusal"

        client = MagicMock()
        client.messages.create.return_value = response

        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(VisionAPIError):
                estimate_crop(self._thumb(d), client)


if __name__ == "__main__":
    unittest.main()
