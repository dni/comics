import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from comics_importer.errors import VisionAPIError
from comics_importer.vision import COMIC_METADATA_SCHEMA, identify_metadata


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


if __name__ == "__main__":
    unittest.main()
