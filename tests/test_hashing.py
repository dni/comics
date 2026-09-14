import tempfile
import unittest
from pathlib import Path

from comics_importer.hashing import compute_content_hash


class TestHashing(unittest.TestCase):
    def test_same_content_same_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p1 = Path(d) / "a.jpg"
            p2 = Path(d) / "b.jpg"
            p1.write_bytes(b"hello world")
            p2.write_bytes(b"hello world")
            self.assertEqual(compute_content_hash(p1), compute_content_hash(p2))

    def test_different_content_different_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p1 = Path(d) / "a.jpg"
            p2 = Path(d) / "b.jpg"
            p1.write_bytes(b"hello world")
            p2.write_bytes(b"goodbye world")
            self.assertNotEqual(compute_content_hash(p1), compute_content_hash(p2))

    def test_large_file_chunked_read(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "big.jpg"
            p.write_bytes(b"x" * (3 * 1024 * 1024))
            digest = compute_content_hash(p)
            self.assertEqual(len(digest), 64)


if __name__ == "__main__":
    unittest.main()
