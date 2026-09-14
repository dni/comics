import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import create_app
from comics_importer import db
from comics_importer.hashing import compute_content_hash


class TestFrontendServing(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.db_path = self.tmpdir / "catalog.db"
        self.library_dir = self.tmpdir / "library"
        self.library_dir.mkdir()

        self.frontend_dist = self.tmpdir / "dist"
        (self.frontend_dist / "assets").mkdir(parents=True)
        (self.frontend_dist / "index.html").write_text("<html>spa shell</html>")
        (self.frontend_dist / "assets" / "app.js").write_text("console.log('hi')")
        (self.frontend_dist / "favicon.svg").write_text("<svg/>")

        self.app = create_app(self.db_path, self.library_dir, frontend_dist=self.frontend_dist)
        self.client = TestClient(self.app)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_root_serves_index_html(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("spa shell", resp.text)

    def test_unmatched_client_route_falls_back_to_index_html(self):
        # e.g. a hard refresh on /comic/5, a solid-router client-side route
        resp = self.client.get("/comic/5")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("spa shell", resp.text)

    def test_actual_static_file_is_served_directly(self):
        resp = self.client.get("/favicon.svg")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("<svg/>", resp.text)

    def test_asset_bundle_served_from_assets_mount(self):
        resp = self.client.get("/assets/app.js")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("console.log", resp.text)

    def test_api_routes_are_not_shadowed_by_spa_fallback(self):
        resp = self.client.get("/api/auth/status")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("has_admin", resp.json())


class TestBackend(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.db_path = self.tmpdir / "catalog.db"
        self.library_dir = self.tmpdir / "library"
        self.library_dir.mkdir()

        conn = db.get_connection(self.db_path)
        db.init_db(conn)

        series_dir = self.library_dir / "Goofy"
        series_dir.mkdir()
        self.image_path = series_dir / "Goofy #1 (1990).jpg"
        self.image_path.write_bytes(b"fake-jpeg-bytes")

        self.comic_id = db.upsert_comic(
            conn,
            content_hash="hash1",
            original_filename="orig.jpg",
            original_path="/import/orig.jpg",
            series="Goofy",
            issue_number="1",
            year=1990,
            publisher="Egmont",
            confidence="high",
            optimized_image_path=str(self.image_path),
            status="processed",
        )

        db.upsert_comic(
            conn,
            content_hash="hash2",
            original_filename="failed.jpg",
            original_path="/import/failed/failed.jpg",
            status="failed",
            error_message="boom",
        )
        conn.close()

        self.app = create_app(self.db_path, self.library_dir)
        self.client = TestClient(self.app)
        self.client.post("/api/auth/setup", json={"username": "admin", "password": "testpassword123"})

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_list_comics_returns_only_processed(self):
        resp = self.client.get("/api/comics")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["series"], "Goofy")
        self.assertTrue(data[0]["image_url"].startswith("/library/Goofy/Goofy%20%231%20%281990%29.jpg?v="))

    def test_list_comics_search(self):
        resp = self.client.get("/api/comics", params={"q": "egmont"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

        resp = self.client.get("/api/comics", params={"q": "nonexistent"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_get_comic(self):
        resp = self.client.get(f"/api/comics/{self.comic_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["series"], "Goofy")

    def test_get_comic_missing_returns_404(self):
        resp = self.client.get("/api/comics/9999")
        self.assertEqual(resp.status_code, 404)

    def test_library_image_served(self):
        image_url = self.client.get(f"/api/comics/{self.comic_id}").json()["image_url"]
        resp = self.client.get(image_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b"fake-jpeg-bytes")

    def test_patch_updates_field_without_rename(self):
        resp = self.client.patch(f"/api/comics/{self.comic_id}", json={"notes": "spine crease"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["notes"], "spine crease")
        self.assertTrue(self.image_path.exists())
        self.assertTrue(
            resp.json()["image_url"].startswith("/library/Goofy/Goofy%20%231%20%281990%29.jpg?v=")
        )

    def test_patch_renames_file_when_series_changes(self):
        resp = self.client.patch(f"/api/comics/{self.comic_id}", json={"series": "Donald Duck"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["series"], "Donald Duck")

        new_path = self.library_dir / "Donald Duck" / "Donald Duck #1 (1990).jpg"
        self.assertTrue(new_path.exists())
        self.assertFalse(self.image_path.exists())

        conn = db.get_connection(self.db_path)
        row = db.get_comic(conn, self.comic_id)
        conn.close()
        self.assertEqual(row["optimized_image_path"], str(new_path))

    def test_patch_missing_comic_returns_404(self):
        resp = self.client.patch("/api/comics/9999", json={"notes": "x"})
        self.assertEqual(resp.status_code, 404)

    def test_update_storage_location(self):
        resp = self.client.patch(f"/api/comics/{self.comic_id}", json={"storage_location": "Box 3, Row B"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["storage_location"], "Box 3, Row B")

    def test_upload_image_overwrites_file_in_place(self):
        original_url = self.client.get(f"/api/comics/{self.comic_id}").json()["image_url"]

        resp = self.client.post(
            f"/api/comics/{self.comic_id}/image",
            files={"file": ("cropped.jpg", b"cropped-bytes", "image/jpeg")},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()

        # same on-disk path, new bytes
        self.assertEqual(self.image_path.read_bytes(), b"cropped-bytes")
        conn = db.get_connection(self.db_path)
        row = db.get_comic(conn, self.comic_id)
        conn.close()
        self.assertEqual(row["optimized_image_path"], str(self.image_path))

        # cache-busting query param must change so the browser refetches
        self.assertNotEqual(body["image_url"], original_url)
        self.assertTrue(body["image_url"].startswith(original_url.split("?")[0] + "?v="))

    def test_upload_image_missing_comic_returns_404(self):
        resp = self.client.post(
            "/api/comics/9999/image", files={"file": ("x.jpg", b"data", "image/jpeg")}
        )
        self.assertEqual(resp.status_code, 404)

    def test_reclassify_missing_comic_returns_404(self):
        resp = self.client.post("/api/comics/9999/reclassify")
        self.assertEqual(resp.status_code, 404)

    def test_reclassify_no_image_returns_400(self):
        conn = db.get_connection(self.db_path)
        no_image_id = db.upsert_comic(
            conn, content_hash="h-no-image", original_filename="x.jpg",
            original_path="/import/x.jpg", status="processed",
        )
        conn.close()
        resp = self.client.post(f"/api/comics/{no_image_id}/reclassify")
        self.assertEqual(resp.status_code, 400)

    @patch("backend.main.check_imagemagick_available", lambda: None)
    @patch("backend.main.make_thumbnail", lambda src, dst: dst.write_bytes(b"thumb"))
    @patch("backend.main.identify_metadata")
    def test_reclassify_success_updates_metadata_and_renames(self, mock_identify):
        mock_identify.return_value = (
            {
                "series": "Donald Duck",
                "issue_number": "1",
                "year": 1991,
                "publisher": "Marvel",
                "language": "en",
                "condition_grade": "Fine",
                "numeric_grade": 6.0,
                "confidence": "high",
                "notes": "re-read",
                "rotation_degrees": 1.5,
                "crop_left": 0.1,
                "crop_top": 0.1,
                "crop_width": 0.8,
                "crop_height": 0.8,
            },
            '{"series": "Donald Duck"}',
        )

        resp = self.client.post(f"/api/comics/{self.comic_id}/reclassify")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["series"], "Donald Duck")
        self.assertEqual(body["confidence"], "high")
        self.assertEqual(body["numeric_grade"], 6.0)
        self.assertEqual(body["suggested_rotation_degrees"], 1.5)

        # file moved to match the new series/issue/year
        new_path = self.library_dir / "Donald Duck" / "Donald Duck #1 (1991).jpg"
        self.assertTrue(new_path.exists())
        self.assertFalse(self.image_path.exists())

    @patch("backend.main.check_imagemagick_available", lambda: None)
    @patch("backend.main.make_thumbnail", lambda src, dst: dst.write_bytes(b"thumb"))
    @patch("backend.main.identify_metadata")
    def test_reclassify_vision_error_returns_502(self, mock_identify):
        from comics_importer.errors import VisionAPIError

        mock_identify.side_effect = VisionAPIError("model refused")
        resp = self.client.post(f"/api/comics/{self.comic_id}/reclassify")
        self.assertEqual(resp.status_code, 502)

    def test_delete_comic_removes_row_and_file(self):
        self.assertTrue(self.image_path.exists())

        resp = self.client.delete(f"/api/comics/{self.comic_id}")
        self.assertEqual(resp.status_code, 204)

        self.assertFalse(self.image_path.exists())
        # empty series folder pruned too
        self.assertFalse(self.image_path.parent.exists())

        conn = db.get_connection(self.db_path)
        self.assertIsNone(db.get_comic(conn, self.comic_id))
        conn.close()

        # the comic no longer appears in listings
        resp = self.client.get("/api/comics")
        self.assertEqual(resp.json(), [])

    def test_delete_comic_missing_returns_404(self):
        resp = self.client.delete("/api/comics/9999")
        self.assertEqual(resp.status_code, 404)

    def test_delete_comic_without_image_only_removes_row(self):
        conn = db.get_connection(self.db_path)
        no_image_id = db.upsert_comic(
            conn, content_hash="h-no-image-del", original_filename="x.jpg",
            original_path="/import/x.jpg", status="processed",
        )
        conn.close()

        resp = self.client.delete(f"/api/comics/{no_image_id}")
        self.assertEqual(resp.status_code, 204)

        conn = db.get_connection(self.db_path)
        self.assertIsNone(db.get_comic(conn, no_image_id))
        conn.close()

    def test_list_failed_returns_only_failed(self):
        resp = self.client.get("/api/failed")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["original_filename"], "failed.jpg")
        self.assertEqual(data[0]["error_message"], "boom")

    def test_retry_failed_missing_returns_404(self):
        resp = self.client.post("/api/failed/9999/retry")
        self.assertEqual(resp.status_code, 404)

    def test_retry_failed_missing_file_returns_400(self):
        conn = db.get_connection(self.db_path)
        failed_row = db.find_by_hash(conn, "hash2")
        conn.close()
        # original_path ("/import/failed/failed.jpg") does not exist on disk in this fixture
        resp = self.client.post(f"/api/failed/{failed_row['id']}/retry")
        self.assertEqual(resp.status_code, 400)

    @patch("backend.main.check_imagemagick_available", lambda: None)
    @patch("backend.main.process_and_record")
    def test_retry_failed_success(self, mock_process):
        failed_dir = self.tmpdir / "import" / "failed"
        failed_dir.mkdir(parents=True)
        real_path = failed_dir / "failed.jpg"
        real_path.write_bytes(b"retry-bytes")

        conn = db.get_connection(self.db_path)
        failed_row = db.find_by_hash(conn, "hash2")
        db.update_comic_fields(conn, failed_row["id"], optimized_image_path=None)
        # align content_hash with the real file bytes: process_and_record recomputes the
        # hash from disk, and must match this row (by content_hash) for the retry to
        # update it in place rather than inserting a second row
        conn.execute(
            "UPDATE comics SET original_path = ?, content_hash = ? WHERE id = ?",
            (str(real_path), compute_content_hash(real_path), failed_row["id"]),
        )
        conn.commit()
        conn.close()

        def fake_success(src_path, *, import_dir, library_dir, conn, client, dry_run):
            content_hash = compute_content_hash(src_path)
            dest = library_dir / "Goofy" / "Goofy #99 (2000).jpg"
            dest.parent.mkdir(parents=True, exist_ok=True)
            src_path.rename(dest)
            db.upsert_comic(
                conn,
                content_hash=content_hash,
                original_filename=src_path.name,
                original_path=str(src_path),
                series="Goofy",
                issue_number="99",
                year=2000,
                optimized_image_path=str(dest),
                status="processed",
            )
            return "processed", None

        mock_process.side_effect = fake_success

        resp = self.client.post(f"/api/failed/{failed_row['id']}/retry")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "processed")
        self.assertEqual(body["comic"]["series"], "Goofy")

        # same row (matched by content_hash), no longer failed
        conn = db.get_connection(self.db_path)
        row = db.get_comic(conn, failed_row["id"])
        conn.close()
        self.assertEqual(row["status"], "processed")

    def test_export_csv(self):
        resp = self.client.get("/api/export/csv")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"].split(";")[0], "text/csv")
        body = resp.text
        self.assertIn("series", body.splitlines()[0])
        self.assertIn("Goofy", body)
        self.assertNotIn("Donald", body)  # failed row must not appear in export

    def test_export_backup_is_valid_zip_with_db_and_images(self):
        import zipfile
        import io as _io

        resp = self.client.get("/api/export/backup")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "application/zip")

        zf = zipfile.ZipFile(_io.BytesIO(resp.content))
        names = zf.namelist()
        self.assertIn("catalog.db", names)
        self.assertTrue(any(n.startswith("library/Goofy/") for n in names))

    def test_list_comics_confidence_filter(self):
        resp = self.client.get("/api/comics", params={"confidence": "high"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

        resp = self.client.get("/api/comics", params={"confidence": "low"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_get_comic_reports_duplicate_of(self):
        conn = db.get_connection(self.db_path)
        db.upsert_comic(
            conn,
            content_hash="hash3",
            original_filename="dup.jpg",
            original_path="/import/dup.jpg",
            series="goofy",
            issue_number="1",
            year=1991,
            publisher="Egmont",
            condition_grade="Fine",
            numeric_grade=6.5,
            status="processed",
        )
        conn.close()

        resp = self.client.get(f"/api/comics/{self.comic_id}")
        self.assertEqual(resp.status_code, 200)
        dupes = resp.json()["duplicate_of"]
        self.assertEqual(len(dupes), 1)
        self.assertEqual(dupes[0]["series"], "goofy")
        # enriched with enough context (grade/condition/publisher) to tell
        # "this is my second copy" apart from "I scanned the same book twice"
        self.assertEqual(dupes[0]["condition_grade"], "Fine")
        self.assertEqual(dupes[0]["numeric_grade"], 6.5)
        self.assertEqual(dupes[0]["publisher"], "Egmont")

    def test_list_comics_does_not_compute_duplicate_of(self):
        # duplicate_of is intentionally skipped in the list view for performance;
        # verify it defaults to an empty list rather than erroring
        resp = self.client.get("/api/comics")
        self.assertEqual(resp.json()[0]["duplicate_of"], [])


class TestAuth(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.db_path = self.tmpdir / "catalog.db"
        self.library_dir = self.tmpdir / "library"
        self.library_dir.mkdir()

        conn = db.get_connection(self.db_path)
        db.init_db(conn)
        db.upsert_comic(
            conn,
            content_hash="hash1",
            original_filename="orig.jpg",
            original_path="/import/orig.jpg",
            series="Goofy",
            status="processed",
        )
        conn.close()

        self.app = create_app(self.db_path, self.library_dir)
        self.client = TestClient(self.app)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_status_reports_no_admin_initially(self):
        resp = self.client.get("/api/auth/status")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["has_admin"])

    def test_protected_endpoint_requires_auth(self):
        resp = self.client.get("/api/comics")
        self.assertEqual(resp.status_code, 401)

    def test_setup_creates_account_and_logs_in(self):
        resp = self.client.post("/api/auth/setup", json={"username": "admin", "password": "hunter2pass"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["username"], "admin")

        # session cookie from setup should already grant access
        resp = self.client.get("/api/comics")
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get("/api/auth/status")
        self.assertTrue(resp.json()["has_admin"])

    def test_setup_rejects_short_password(self):
        resp = self.client.post("/api/auth/setup", json={"username": "admin", "password": "short"})
        self.assertEqual(resp.status_code, 400)

    def test_setup_twice_returns_409(self):
        self.client.post("/api/auth/setup", json={"username": "admin", "password": "hunter2pass"})
        resp = self.client.post("/api/auth/setup", json={"username": "someoneelse", "password": "hunter2pass"})
        self.assertEqual(resp.status_code, 409)

    def test_login_with_correct_credentials(self):
        self.client.post("/api/auth/setup", json={"username": "admin", "password": "hunter2pass"})
        self.client.post("/api/auth/logout")

        resp = self.client.post("/api/auth/login", json={"username": "admin", "password": "hunter2pass"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.client.get("/api/comics").status_code, 200)

    def test_login_with_wrong_password_returns_401(self):
        self.client.post("/api/auth/setup", json={"username": "admin", "password": "hunter2pass"})
        self.client.post("/api/auth/logout")

        resp = self.client.post("/api/auth/login", json={"username": "admin", "password": "wrongpass"})
        self.assertEqual(resp.status_code, 401)

    def test_logout_revokes_access(self):
        self.client.post("/api/auth/setup", json={"username": "admin", "password": "hunter2pass"})
        self.client.post("/api/auth/logout")
        resp = self.client.get("/api/comics")
        self.assertEqual(resp.status_code, 401)

    def test_me_reflects_current_session(self):
        resp = self.client.get("/api/auth/me")
        self.assertEqual(resp.status_code, 401)

        self.client.post("/api/auth/setup", json={"username": "admin", "password": "hunter2pass"})
        resp = self.client.get("/api/auth/me")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["username"], "admin")

    def test_public_for_sale_requires_no_auth(self):
        resp = self.client.get("/api/public/for-sale")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_public_for_sale_only_lists_marked_comics(self):
        conn = db.get_connection(self.db_path)
        row = db.find_by_hash(conn, "hash1")
        db.update_comic_fields(conn, row["id"], for_sale=True, asking_price=25.0)
        conn.close()

        resp = self.client.get("/api/public/for-sale")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["series"], "Goofy")
        self.assertEqual(data[0]["asking_price"], 25.0)
        # public payload must not leak owner-only fields
        self.assertNotIn("storage_location", data[0])
        self.assertNotIn("original_filename", data[0])


class TestImportEndpoint(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.db_path = self.tmpdir / "catalog.db"
        self.library_dir = self.tmpdir / "library"
        self.import_dir = self.tmpdir / "import"
        self.library_dir.mkdir()
        self.import_dir.mkdir()

        conn = db.get_connection(self.db_path)
        db.init_db(conn)
        conn.close()

        self.app = create_app(self.db_path, self.library_dir, self.import_dir)
        self.client = TestClient(self.app)
        self.client.post("/api/auth/setup", json={"username": "admin", "password": "testpassword123"})

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _fake_success(self, src_path, *, import_dir, library_dir, conn, client, dry_run):
        content_hash = compute_content_hash(src_path)
        dest = library_dir / "Goofy" / "Goofy #1 (1990).jpg"
        dest.parent.mkdir(parents=True, exist_ok=True)
        src_path.rename(dest)
        db.upsert_comic(
            conn,
            content_hash=content_hash,
            original_filename=src_path.name,
            original_path=str(src_path),
            series="Goofy",
            issue_number="1",
            year=1990,
            optimized_image_path=str(dest),
            status="processed",
        )
        return "processed", None

    @patch("backend.main.check_imagemagick_available", lambda: None)
    @patch("backend.main.process_and_record")
    def test_import_success(self, mock_process):
        mock_process.side_effect = self._fake_success

        resp = self.client.post(
            "/api/import", files={"file": ("photo.jpg", b"fake-image-bytes", "image/jpeg")}
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "processed")
        self.assertEqual(body["comic"]["series"], "Goofy")
        self.assertEqual(body["filename"], "photo.jpg")

        # the uploaded staging file should not linger in import/ once processed
        self.assertEqual(list(self.import_dir.glob("*.jpg")), [])

    @patch("backend.main.check_imagemagick_available", lambda: None)
    @patch("backend.main.process_and_record")
    def test_import_failure_reports_error_without_http_error(self, mock_process):
        mock_process.return_value = ("failed", RuntimeError("ImageMagick blew up"))

        resp = self.client.post("/api/import", files={"file": ("bad.jpg", b"junk", "image/jpeg")})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "failed")
        self.assertIn("ImageMagick blew up", body["error"])
        self.assertIsNone(body["comic"])

    @patch("backend.main.check_imagemagick_available", lambda: None)
    @patch("backend.main.process_and_record")
    def test_import_skips_duplicate_upload(self, mock_process):
        mock_process.side_effect = self._fake_success

        first = self.client.post(
            "/api/import", files={"file": ("photo.jpg", b"same-bytes", "image/jpeg")}
        )
        self.assertEqual(first.json()["status"], "processed")
        mock_process.reset_mock()

        second = self.client.post(
            "/api/import", files={"file": ("photo-again.jpg", b"same-bytes", "image/jpeg")}
        )
        self.assertEqual(second.status_code, 200)
        body = second.json()
        self.assertEqual(body["status"], "skipped")
        self.assertEqual(body["comic"]["series"], "Goofy")
        mock_process.assert_not_called()

        # the re-uploaded duplicate should be cleaned up, not left in import/
        self.assertEqual(list(self.import_dir.glob("*.jpg")), [])

    def test_import_rejects_unsupported_extension(self):
        resp = self.client.post(
            "/api/import", files={"file": ("notes.txt", b"hello", "text/plain")}
        )
        self.assertEqual(resp.status_code, 400)

    @patch("backend.main.check_imagemagick_available", lambda: None)
    @patch("anthropic.Anthropic", side_effect=RuntimeError("no credentials"))
    def test_import_without_api_key_returns_503(self, mock_anthropic):
        resp = self.client.post(
            "/api/import", files={"file": ("photo.jpg", b"data", "image/jpeg")}
        )
        self.assertEqual(resp.status_code, 503)


if __name__ == "__main__":
    unittest.main()
