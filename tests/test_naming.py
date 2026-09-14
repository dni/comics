import tempfile
import unittest
from pathlib import Path

from comics_importer.naming import build_library_path, dedupe_path, sanitize_component


class TestSanitizeComponent(unittest.TestCase):
    def test_none_returns_unknown(self):
        self.assertEqual(sanitize_component(None), "Unknown")

    def test_empty_returns_unknown(self):
        self.assertEqual(sanitize_component("   "), "Unknown")

    def test_replaces_unsafe_chars(self):
        self.assertEqual(sanitize_component('Spider-Man: Homecoming/Part*2?'), "Spider-Man_ Homecoming_Part_2_")

    def test_collapses_whitespace(self):
        self.assertEqual(sanitize_component("Micky   Maus\n\t"), "Micky Maus")


class TestDedupePath(unittest.TestCase):
    def test_returns_same_path_if_not_exists(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "foo.jpg"
            self.assertEqual(dedupe_path(p), p)

    def test_appends_counter_on_collision(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "foo.jpg"
            p.write_bytes(b"x")
            result = dedupe_path(p)
            self.assertEqual(result, Path(d) / "foo (2).jpg")

    def test_increments_past_multiple_collisions(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "foo.jpg").write_bytes(b"x")
            (Path(d) / "foo (2).jpg").write_bytes(b"x")
            (Path(d) / "foo (3).jpg").write_bytes(b"x")
            result = dedupe_path(Path(d) / "foo.jpg")
            self.assertEqual(result, Path(d) / "foo (4).jpg")


class TestBuildLibraryPath(unittest.TestCase):
    def test_full_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            lib = Path(d)
            result = build_library_path("Amazing Spider-Man", "1", 1963, lib)
            self.assertEqual(result, lib / "Amazing Spider-Man" / "Amazing Spider-Man #1 (1963).jpg")

    def test_missing_year_omits_suffix(self):
        with tempfile.TemporaryDirectory() as d:
            lib = Path(d)
            result = build_library_path("Micky Maus", "42", None, lib)
            self.assertEqual(result, lib / "Micky Maus" / "Micky Maus #42.jpg")

    def test_missing_series_falls_back(self):
        with tempfile.TemporaryDirectory() as d:
            lib = Path(d)
            result = build_library_path(None, None, None, lib)
            self.assertEqual(result, lib / "Unknown Series" / "Unknown Series #Unknown.jpg")

    def test_collision_dedupes(self):
        with tempfile.TemporaryDirectory() as d:
            lib = Path(d)
            target_dir = lib / "Goofy"
            target_dir.mkdir(parents=True)
            (target_dir / "Goofy #1 (1990).jpg").write_bytes(b"x")
            result = build_library_path("Goofy", "1", 1990, lib)
            self.assertEqual(result, target_dir / "Goofy #1 (1990) (2).jpg")

    def test_ignore_path_excludes_its_own_current_file_from_collision(self):
        with tempfile.TemporaryDirectory() as d:
            lib = Path(d)
            existing = lib / "Goofy" / "Goofy #1 (1990).jpg"
            existing.parent.mkdir(parents=True)
            existing.write_bytes(b"x")
            result = build_library_path("Goofy", "1", 1990, lib, ignore_path=existing)
            self.assertEqual(result, existing)

    def test_ignore_path_still_dedupes_against_other_files(self):
        with tempfile.TemporaryDirectory() as d:
            lib = Path(d)
            existing = lib / "Goofy" / "Goofy #1 (1990).jpg"
            existing.parent.mkdir(parents=True)
            existing.write_bytes(b"x")
            other = lib / "Donald Duck" / "Donald Duck #1 (1990).jpg"
            other.parent.mkdir(parents=True)
            other.write_bytes(b"x")
            result = build_library_path("Donald Duck", "1", 1990, lib, ignore_path=existing)
            self.assertEqual(result, other.parent / "Donald Duck #1 (1990) (2).jpg")


if __name__ == "__main__":
    unittest.main()
