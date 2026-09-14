import unittest

from comics_importer import db


class TestDb(unittest.TestCase):
    def setUp(self):
        self.conn = db.get_connection(":memory:")
        db.init_db(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_init_db_is_idempotent(self):
        db.init_db(self.conn)  # should not raise on second call
        cur = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comics'")
        self.assertIsNotNone(cur.fetchone())

    def test_find_by_hash_missing_returns_none(self):
        self.assertIsNone(db.find_by_hash(self.conn, "nonexistent"))

    def test_upsert_then_find(self):
        row_id = db.upsert_comic(
            self.conn,
            content_hash="abc123",
            original_filename="foo.jpg",
            original_path="/import/foo.jpg",
            series="Goofy",
            issue_number="1",
            year=1990,
            status="processed",
        )
        self.assertIsInstance(row_id, int)
        row = db.find_by_hash(self.conn, "abc123")
        self.assertEqual(row["series"], "Goofy")
        self.assertEqual(row["status"], "processed")

    def test_upsert_conflict_updates_existing_row(self):
        db.upsert_comic(
            self.conn,
            content_hash="abc123",
            original_filename="foo.jpg",
            original_path="/import/foo.jpg",
            status="failed",
            error_message="boom",
        )
        db.upsert_comic(
            self.conn,
            content_hash="abc123",
            original_filename="foo.jpg",
            original_path="/import/foo.jpg",
            series="Goofy",
            status="processed",
            error_message=None,
        )
        row = db.find_by_hash(self.conn, "abc123")
        self.assertEqual(row["status"], "processed")
        self.assertIsNone(row["error_message"])
        self.assertEqual(row["series"], "Goofy")

        # still only one row for this hash
        cur = self.conn.execute("SELECT COUNT(*) as c FROM comics WHERE content_hash = ?", ("abc123",))
        self.assertEqual(cur.fetchone()["c"], 1)

    def test_list_comics_defaults_to_processed_only(self):
        db.upsert_comic(self.conn, content_hash="h1", original_filename="a.jpg",
                         original_path="/x/a.jpg", series="Goofy", status="processed")
        db.upsert_comic(self.conn, content_hash="h2", original_filename="b.jpg",
                         original_path="/x/b.jpg", series="Donald Duck", status="failed")
        rows = db.list_comics(self.conn)
        self.assertEqual([r["series"] for r in rows], ["Goofy"])

    def test_list_comics_search_matches_series_issue_or_publisher(self):
        db.upsert_comic(self.conn, content_hash="h1", original_filename="a.jpg", original_path="/x/a.jpg",
                         series="Goofy", issue_number="1", publisher="Egmont", status="processed")
        db.upsert_comic(self.conn, content_hash="h2", original_filename="b.jpg", original_path="/x/b.jpg",
                         series="Donald Duck", issue_number="1", publisher="Marvel", status="processed")
        rows = db.list_comics(self.conn, q="egmont")
        self.assertEqual([r["series"] for r in rows], ["Goofy"])

    def test_list_comics_sort_and_order(self):
        db.upsert_comic(self.conn, content_hash="h1", original_filename="a.jpg", original_path="/x/a.jpg",
                         series="Zorro", status="processed")
        db.upsert_comic(self.conn, content_hash="h2", original_filename="b.jpg", original_path="/x/b.jpg",
                         series="Astro Boy", status="processed")
        rows = db.list_comics(self.conn, sort_by="series", order="asc")
        self.assertEqual([r["series"] for r in rows], ["Astro Boy", "Zorro"])
        rows = db.list_comics(self.conn, sort_by="series", order="desc")
        self.assertEqual([r["series"] for r in rows], ["Zorro", "Astro Boy"])

    def test_list_comics_rejects_unknown_sort_column(self):
        db.upsert_comic(self.conn, content_hash="h1", original_filename="a.jpg", original_path="/x/a.jpg",
                         series="Goofy", status="processed")
        # falls back to sorting by series instead of raising / injecting arbitrary SQL
        rows = db.list_comics(self.conn, sort_by="id; DROP TABLE comics; --")
        self.assertEqual(len(rows), 1)

    def test_get_comic_by_id(self):
        row_id = db.upsert_comic(self.conn, content_hash="h1", original_filename="a.jpg",
                                  original_path="/x/a.jpg", series="Goofy", status="processed")
        row = db.get_comic(self.conn, row_id)
        self.assertEqual(row["series"], "Goofy")

    def test_get_comic_missing_returns_none(self):
        self.assertIsNone(db.get_comic(self.conn, 999))

    def test_update_comic_fields(self):
        row_id = db.upsert_comic(self.conn, content_hash="h1", original_filename="a.jpg",
                                  original_path="/x/a.jpg", series="Goofy", status="processed")
        db.update_comic_fields(self.conn, row_id, series="Donald Duck", notes="edited")
        row = db.get_comic(self.conn, row_id)
        self.assertEqual(row["series"], "Donald Duck")
        self.assertEqual(row["notes"], "edited")

    def test_update_comic_fields_ignores_unknown_keys(self):
        row_id = db.upsert_comic(self.conn, content_hash="h1", original_filename="a.jpg",
                                  original_path="/x/a.jpg", series="Goofy", status="processed")
        db.update_comic_fields(self.conn, row_id, content_hash="should-not-change", series="X")
        row = db.get_comic(self.conn, row_id)
        self.assertEqual(row["content_hash"], "h1")
        self.assertEqual(row["series"], "X")

    def test_list_comics_confidence_filter(self):
        db.upsert_comic(self.conn, content_hash="h1", original_filename="a.jpg", original_path="/x/a.jpg",
                         series="Goofy", confidence="high", status="processed")
        db.upsert_comic(self.conn, content_hash="h2", original_filename="b.jpg", original_path="/x/b.jpg",
                         series="Donald Duck", confidence="low", status="processed")
        rows = db.list_comics(self.conn, confidence="low")
        self.assertEqual([r["series"] for r in rows], ["Donald Duck"])

    def test_list_comics_ignores_invalid_confidence_value(self):
        db.upsert_comic(self.conn, content_hash="h1", original_filename="a.jpg", original_path="/x/a.jpg",
                         series="Goofy", confidence="high", status="processed")
        rows = db.list_comics(self.conn, confidence="'; DROP TABLE comics; --")
        self.assertEqual(len(rows), 1)

    def test_list_failed_comics(self):
        db.upsert_comic(self.conn, content_hash="h1", original_filename="a.jpg", original_path="/x/a.jpg",
                         status="processed")
        db.upsert_comic(self.conn, content_hash="h2", original_filename="b.jpg",
                         original_path="/import/failed/b.jpg", status="failed", error_message="boom")
        rows = db.list_failed_comics(self.conn)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["original_filename"], "b.jpg")
        self.assertEqual(rows[0]["error_message"], "boom")

    def test_find_duplicate_candidates_matches_case_insensitively(self):
        id1 = db.upsert_comic(self.conn, content_hash="h1", original_filename="a.jpg", original_path="/x/a.jpg",
                               series="Goofy", issue_number="1", status="processed")
        db.upsert_comic(self.conn, content_hash="h2", original_filename="b.jpg", original_path="/x/b.jpg",
                         series="goofy", issue_number="1", status="processed")
        dupes = db.find_duplicate_candidates(self.conn, id1, "Goofy", "1")
        self.assertEqual(len(dupes), 1)
        self.assertEqual(dupes[0]["series"], "goofy")

    def test_find_duplicate_candidates_none_when_unique(self):
        id1 = db.upsert_comic(self.conn, content_hash="h1", original_filename="a.jpg", original_path="/x/a.jpg",
                               series="Goofy", issue_number="1", status="processed")
        dupes = db.find_duplicate_candidates(self.conn, id1, "Goofy", "1")
        self.assertEqual(dupes, [])

    def test_find_duplicate_candidates_requires_series_and_issue(self):
        id1 = db.upsert_comic(self.conn, content_hash="h1", original_filename="a.jpg", original_path="/x/a.jpg",
                               status="processed")
        self.assertEqual(db.find_duplicate_candidates(self.conn, id1, None, "1"), [])
        self.assertEqual(db.find_duplicate_candidates(self.conn, id1, "Goofy", None), [])

    def test_list_all_comics_for_export(self):
        db.upsert_comic(self.conn, content_hash="h1", original_filename="a.jpg", original_path="/x/a.jpg",
                         series="Goofy", status="processed")
        db.upsert_comic(self.conn, content_hash="h2", original_filename="b.jpg", original_path="/x/b.jpg",
                         series="Donald Duck", status="failed")
        rows = db.list_all_comics_for_export(self.conn)
        self.assertEqual([r["series"] for r in rows], ["Goofy"])


if __name__ == "__main__":
    unittest.main()
