import argparse
import csv
import io
import os
import secrets
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.background import BackgroundTask
from starlette.middleware.sessions import SessionMiddleware

from backend import auth
from comics_importer import config, db, naming
from comics_importer.errors import ImageMagickNotFoundError, VisionAPIError
from comics_importer.hashing import compute_content_hash
from comics_importer.imagemagick import check_imagemagick_available, make_thumbnail
from comics_importer.pipeline import process_and_record
from comics_importer.vision import identify_metadata

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

_SORT_COLUMNS = {"series", "issue_number", "year", "confidence", "imported_at", "updated_at"}


class DuplicateRef(BaseModel):
    id: int
    series: Optional[str] = None
    issue_number: Optional[str] = None
    year: Optional[int] = None
    publisher: Optional[str] = None
    condition_grade: Optional[str] = None
    numeric_grade: Optional[float] = None


class ComicOut(BaseModel):
    id: int
    series: Optional[str] = None
    issue_number: Optional[str] = None
    year: Optional[int] = None
    publisher: Optional[str] = None
    language: Optional[str] = None
    condition_grade: Optional[str] = None
    numeric_grade: Optional[float] = None
    confidence: Optional[str] = None
    notes: Optional[str] = None
    storage_location: Optional[str] = None
    suggested_rotation_degrees: Optional[float] = None
    suggested_crop_left: Optional[float] = None
    suggested_crop_top: Optional[float] = None
    suggested_crop_width: Optional[float] = None
    suggested_crop_height: Optional[float] = None
    for_sale: bool = False
    asking_price: Optional[float] = None
    ebay_listing_url: Optional[str] = None
    ebay_listing_status: Optional[str] = None
    duplicate_of: list[DuplicateRef] = []
    image_url: Optional[str] = None
    original_filename: str
    imported_at: str


class FailedComicOut(BaseModel):
    id: int
    original_filename: str
    original_path: str
    error_message: Optional[str] = None
    updated_at: str


class ComicUpdate(BaseModel):
    series: Optional[str] = None
    issue_number: Optional[str] = None
    year: Optional[int] = None
    publisher: Optional[str] = None
    language: Optional[str] = None
    condition_grade: Optional[str] = None
    numeric_grade: Optional[float] = None
    confidence: Optional[str] = None
    notes: Optional[str] = None
    storage_location: Optional[str] = None
    for_sale: Optional[bool] = None
    asking_price: Optional[float] = None
    ebay_listing_url: Optional[str] = None
    ebay_listing_status: Optional[str] = None


class ImportResult(BaseModel):
    status: str  # "processed" | "skipped" | "failed"
    filename: str
    comic: Optional[ComicOut] = None
    error: Optional[str] = None


class PublicComicOut(BaseModel):
    id: int
    series: Optional[str] = None
    issue_number: Optional[str] = None
    year: Optional[int] = None
    publisher: Optional[str] = None
    condition_grade: Optional[str] = None
    numeric_grade: Optional[float] = None
    asking_price: Optional[float] = None
    ebay_listing_url: Optional[str] = None
    image_url: Optional[str] = None


class SetupRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthStatusOut(BaseModel):
    has_admin: bool


class MeOut(BaseModel):
    username: str


class ModelsOut(BaseModel):
    models: list[str]
    default: str


def _get_or_create_session_secret(db_path: Path) -> str:
    conn = db.get_connection(db_path)
    db.init_db(conn)
    secret = db.get_setting(conn, "session_secret")
    if secret is None:
        secret = secrets.token_hex(32)
        db.set_setting(conn, "session_secret", secret)
    conn.close()
    return secret


def create_app(
    db_path: Path,
    library_dir: Path,
    import_dir: Path = Path("import"),
    frontend_dist: Optional[Path] = None,
) -> FastAPI:
    app = FastAPI(title="Comic Catalog API")
    app.state.db_path = db_path
    app.state.library_dir = library_dir
    app.state.import_dir = import_dir
    app.state.anthropic_client = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=_get_or_create_session_secret(db_path),
        session_cookie="comics_session",
        same_site="lax",
        https_only=False,
        max_age=14 * 24 * 3600,
    )

    library_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/library", StaticFiles(directory=str(library_dir)), name="library")

    def get_db():
        conn = db.get_connection(app.state.db_path)
        db.init_db(conn)
        try:
            yield conn
        finally:
            conn.close()

    def require_auth(request: Request) -> None:
        if not request.session.get("user_id"):
            raise HTTPException(status_code=401, detail="Not authenticated")

    def row_to_out(row, conn=None) -> ComicOut:
        image_url = None
        if row["optimized_image_path"]:
            path = Path(row["optimized_image_path"])
            try:
                rel = path.relative_to(app.state.library_dir)
            except ValueError:
                rel = path.resolve().relative_to(app.state.library_dir.resolve())
            # cache-bust: overwriting the file in place (rename or crop) keeps the
            # same URL path, so a version query param is needed to bypass the browser cache
            image_url = "/library/" + quote(rel.as_posix(), safe="/") + "?v=" + quote(row["updated_at"], safe="")

        duplicate_of = []
        if conn is not None:
            for dupe in db.find_duplicate_candidates(conn, row["id"], row["series"], row["issue_number"]):
                duplicate_of.append(
                    DuplicateRef(
                        id=dupe["id"],
                        series=dupe["series"],
                        issue_number=dupe["issue_number"],
                        year=dupe["year"],
                        publisher=dupe["publisher"],
                        condition_grade=dupe["condition_grade"],
                        numeric_grade=dupe["numeric_grade"],
                    )
                )

        return ComicOut(
            id=row["id"],
            series=row["series"],
            issue_number=row["issue_number"],
            year=row["year"],
            publisher=row["publisher"],
            language=row["language"],
            condition_grade=row["condition_grade"],
            numeric_grade=row["numeric_grade"],
            confidence=row["confidence"],
            notes=row["notes"],
            storage_location=row["storage_location"],
            suggested_rotation_degrees=row["suggested_rotation_degrees"],
            suggested_crop_left=row["suggested_crop_left"],
            suggested_crop_top=row["suggested_crop_top"],
            suggested_crop_width=row["suggested_crop_width"],
            suggested_crop_height=row["suggested_crop_height"],
            for_sale=bool(row["for_sale"]),
            asking_price=row["asking_price"],
            ebay_listing_url=row["ebay_listing_url"],
            ebay_listing_status=row["ebay_listing_status"],
            duplicate_of=duplicate_of,
            image_url=image_url,
            original_filename=row["original_filename"],
            imported_at=row["imported_at"],
        )

    @app.get("/api/comics", response_model=list[ComicOut], dependencies=[Depends(require_auth)])
    def list_comics(
        q: str | None = None,
        sort: str = "series",
        order: str = "asc",
        confidence: str | None = None,
        conn=Depends(get_db),
    ):
        if sort not in _SORT_COLUMNS:
            sort = "series"
        if order not in {"asc", "desc"}:
            order = "asc"
        rows = db.list_comics(conn, q=q, sort_by=sort, order=order, confidence=confidence)
        return [row_to_out(r) for r in rows]

    @app.get("/api/public/for-sale", response_model=list[PublicComicOut])
    def public_for_sale(conn=Depends(get_db)):
        rows = db.list_for_sale_comics(conn)
        result = []
        for row in rows:
            comic = row_to_out(row)
            result.append(
                PublicComicOut(
                    id=comic.id,
                    series=comic.series,
                    issue_number=comic.issue_number,
                    year=comic.year,
                    publisher=comic.publisher,
                    condition_grade=comic.condition_grade,
                    numeric_grade=comic.numeric_grade,
                    asking_price=comic.asking_price,
                    ebay_listing_url=comic.ebay_listing_url,
                    image_url=comic.image_url,
                )
            )
        return result

    @app.get("/api/comics/{comic_id}", response_model=ComicOut, dependencies=[Depends(require_auth)])
    def get_comic(comic_id: int, conn=Depends(get_db)):
        row = db.get_comic(conn, comic_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Comic not found")
        return row_to_out(row, conn)

    def rename_if_needed(row, new_series, new_issue, new_year) -> Optional[str]:
        """Moves the comic's file to match new series/issue/year, if those changed.

        Returns the new path (to merge into the caller's field dict) or None if
        nothing moved. Shared by update_comic (user edits) and reclassify_comic
        (AI re-identification).
        """
        old_path = Path(row["optimized_image_path"]) if row["optimized_image_path"] else None
        if old_path is None:
            return None
        new_path = naming.build_library_path(
            new_series, new_issue, new_year, app.state.library_dir, ignore_path=old_path
        )
        if new_path.resolve() == old_path.resolve():
            return None
        new_path.parent.mkdir(parents=True, exist_ok=True)
        old_path.rename(new_path)
        try:
            old_path.parent.rmdir()
        except OSError:
            pass
        return str(new_path)

    @app.patch("/api/comics/{comic_id}", response_model=ComicOut, dependencies=[Depends(require_auth)])
    def update_comic(comic_id: int, patch: ComicUpdate, conn=Depends(get_db)):
        row = db.get_comic(conn, comic_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Comic not found")

        fields = patch.model_dump(exclude_unset=True)

        new_path = rename_if_needed(
            row,
            fields.get("series", row["series"]),
            fields.get("issue_number", row["issue_number"]),
            fields.get("year", row["year"]),
        )
        if new_path is not None:
            fields["optimized_image_path"] = new_path

        db.update_comic_fields(conn, comic_id, **fields)
        updated = db.get_comic(conn, comic_id)
        return row_to_out(updated, conn)

    @app.delete(
        "/api/comics/{comic_id}", status_code=204, dependencies=[Depends(require_auth)]
    )
    def delete_comic(comic_id: int, conn=Depends(get_db)):
        row = db.get_comic(conn, comic_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Comic not found")

        if row["optimized_image_path"]:
            image_path = Path(row["optimized_image_path"])
            if image_path.exists():
                image_path.unlink()
                try:
                    image_path.parent.rmdir()
                except OSError:
                    pass

        db.delete_comic(conn, comic_id)

    @app.post(
        "/api/comics/{comic_id}/image", response_model=ComicOut, dependencies=[Depends(require_auth)]
    )
    def upload_comic_image(comic_id: int, file: UploadFile = File(...), conn=Depends(get_db)):
        row = db.get_comic(conn, comic_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Comic not found")

        if row["optimized_image_path"]:
            dest_path = Path(row["optimized_image_path"])
        else:
            dest_path = naming.build_library_path(
                row["series"], row["issue_number"], row["year"], app.state.library_dir
            )

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with dest_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)

        db.update_comic_fields(
            conn,
            comic_id,
            optimized_image_path=str(dest_path),
            suggested_rotation_degrees=None,
            suggested_crop_left=None,
            suggested_crop_top=None,
            suggested_crop_width=None,
            suggested_crop_height=None,
        )
        updated = db.get_comic(conn, comic_id)
        return row_to_out(updated, conn)

    @app.get("/api/models", response_model=ModelsOut, dependencies=[Depends(require_auth)])
    def list_models():
        return ModelsOut(models=config.AVAILABLE_MODELS, default=config.CLAUDE_MODEL)

    def resolve_model(model: Optional[str]) -> str:
        if not model:
            return config.CLAUDE_MODEL
        if model not in config.AVAILABLE_MODELS:
            raise HTTPException(status_code=400, detail=f"Unknown model: {model}")
        return model

    def get_anthropic_client():
        if app.state.anthropic_client is None:
            try:
                import anthropic

                app.state.anthropic_client = anthropic.Anthropic()
            except Exception as exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"Anthropic client not configured (check ANTHROPIC_API_KEY): {exc}",
                ) from exc
        return app.state.anthropic_client

    @app.post("/api/import", response_model=ImportResult, dependencies=[Depends(require_auth)])
    def import_comic(file: UploadFile = File(...), model: Optional[str] = Form(None), conn=Depends(get_db)):
        original_name = Path(file.filename or "upload.jpg").name or "upload.jpg"
        if Path(original_name).suffix.lower() not in config.SUPPORTED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {original_name}")

        resolved_model = resolve_model(model)

        try:
            check_imagemagick_available()
        except ImageMagickNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        client = get_anthropic_client()

        import_dir = app.state.import_dir
        import_dir.mkdir(parents=True, exist_ok=True)

        dest_path = naming.dedupe_path(import_dir / original_name)
        with dest_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)

        content_hash = compute_content_hash(dest_path)
        existing = db.find_by_hash(conn, content_hash)
        if existing is not None and existing["status"] == "processed":
            dest_path.unlink(missing_ok=True)
            return ImportResult(status="skipped", filename=original_name, comic=row_to_out(existing, conn))

        result, error = process_and_record(
            dest_path,
            import_dir=import_dir,
            library_dir=app.state.library_dir,
            conn=conn,
            client=client,
            dry_run=False,
            model=resolved_model,
        )

        if result == "failed":
            return ImportResult(status="failed", filename=original_name, error=str(error))

        updated = db.find_by_hash(conn, content_hash)
        return ImportResult(
            status=result,
            filename=original_name,
            comic=row_to_out(updated, conn) if updated else None,
        )

    @app.get(
        "/api/failed", response_model=list[FailedComicOut], dependencies=[Depends(require_auth)]
    )
    def list_failed(conn=Depends(get_db)):
        rows = db.list_failed_comics(conn)
        return [
            FailedComicOut(
                id=row["id"],
                original_filename=row["original_filename"],
                original_path=row["original_path"],
                error_message=row["error_message"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @app.post(
        "/api/failed/{comic_id}/retry",
        response_model=ImportResult,
        dependencies=[Depends(require_auth)],
    )
    def retry_failed(comic_id: int, model: Optional[str] = None, conn=Depends(get_db)):
        row = db.get_comic(conn, comic_id)
        if row is None or row["status"] != "failed":
            raise HTTPException(status_code=404, detail="Failed import not found")

        resolved_model = resolve_model(model)

        src_path = Path(row["original_path"])
        if not src_path.exists():
            raise HTTPException(
                status_code=400, detail=f"File no longer exists at {src_path} — cannot retry"
            )

        try:
            check_imagemagick_available()
        except ImageMagickNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        client = get_anthropic_client()

        result, error = process_and_record(
            src_path,
            import_dir=app.state.import_dir,
            library_dir=app.state.library_dir,
            conn=conn,
            client=client,
            dry_run=False,
            model=resolved_model,
        )

        if result == "failed":
            return ImportResult(status="failed", filename=row["original_filename"], error=str(error))

        updated = db.get_comic(conn, comic_id)
        return ImportResult(
            status=result,
            filename=row["original_filename"],
            comic=row_to_out(updated, conn) if updated else None,
        )

    @app.post(
        "/api/comics/{comic_id}/reclassify",
        response_model=ComicOut,
        dependencies=[Depends(require_auth)],
    )
    def reclassify_comic(comic_id: int, model: Optional[str] = None, conn=Depends(get_db)):
        row = db.get_comic(conn, comic_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Comic not found")
        if not row["optimized_image_path"] or not Path(row["optimized_image_path"]).exists():
            raise HTTPException(status_code=400, detail="This comic has no image to reclassify")

        resolved_model = resolve_model(model)

        try:
            check_imagemagick_available()
        except ImageMagickNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        client = get_anthropic_client()

        # re-examines the comic's *current* image (post any crop/rotate the
        # user has since applied), not the original raw photo
        with tempfile.TemporaryDirectory() as work_dir:
            thumb_path = Path(work_dir) / "thumb.jpg"
            try:
                make_thumbnail(Path(row["optimized_image_path"]), thumb_path)
                metadata, raw_json = identify_metadata(thumb_path, client, model=resolved_model)
            except VisionAPIError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        fields = {
            "series": metadata.get("series"),
            "issue_number": metadata.get("issue_number"),
            "year": metadata.get("year"),
            "publisher": metadata.get("publisher"),
            "language": metadata.get("language"),
            "condition_grade": metadata.get("condition_grade"),
            "numeric_grade": metadata.get("numeric_grade"),
            "confidence": metadata.get("confidence"),
            "notes": metadata.get("notes"),
            "suggested_rotation_degrees": metadata.get("rotation_degrees"),
            "suggested_crop_left": metadata.get("crop_left"),
            "suggested_crop_top": metadata.get("crop_top"),
            "suggested_crop_width": metadata.get("crop_width"),
            "suggested_crop_height": metadata.get("crop_height"),
            "claude_raw_response": raw_json,
        }

        new_path = rename_if_needed(row, fields["series"], fields["issue_number"], fields["year"])
        if new_path is not None:
            fields["optimized_image_path"] = new_path

        db.update_comic_fields(conn, comic_id, **fields)
        updated = db.get_comic(conn, comic_id)
        return row_to_out(updated, conn)

    @app.get("/api/export/csv", dependencies=[Depends(require_auth)])
    def export_csv(conn=Depends(get_db)):
        rows = db.list_all_comics_for_export(conn)
        columns = [
            "id",
            "series",
            "issue_number",
            "year",
            "publisher",
            "language",
            "condition_grade",
            "confidence",
            "storage_location",
            "for_sale",
            "asking_price",
            "ebay_listing_url",
            "ebay_listing_status",
            "notes",
            "imported_at",
        ]
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row[col] for col in columns])
        buffer.seek(0)
        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=comics.csv"},
        )

    @app.get("/api/export/backup", dependencies=[Depends(require_auth)])
    def export_backup():
        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        tmp_path = Path(tmp.name)
        tmp.close()

        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if app.state.db_path.exists():
                zf.write(app.state.db_path, arcname="catalog.db")
            for file_path in app.state.library_dir.rglob("*"):
                if file_path.is_file():
                    zf.write(file_path, arcname=str(Path("library") / file_path.relative_to(app.state.library_dir)))

        return FileResponse(
            tmp_path,
            media_type="application/zip",
            filename="comics-backup.zip",
            background=BackgroundTask(tmp_path.unlink, missing_ok=True),
        )

    @app.get("/api/auth/status", response_model=AuthStatusOut)
    def auth_status(conn=Depends(get_db)):
        return AuthStatusOut(has_admin=db.count_users(conn) > 0)

    @app.post("/api/auth/setup", response_model=MeOut)
    def auth_setup(payload: SetupRequest, request: Request, conn=Depends(get_db)):
        if db.count_users(conn) > 0:
            raise HTTPException(status_code=409, detail="An admin account already exists")

        username = payload.username.strip()
        if not username:
            raise HTTPException(status_code=400, detail="Username is required")
        if len(payload.password) < auth.MIN_PASSWORD_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"Password must be at least {auth.MIN_PASSWORD_LENGTH} characters",
            )

        password_hash = auth.hash_password(payload.password)
        user_id = db.create_user(conn, username, password_hash)
        request.session["user_id"] = user_id
        request.session["username"] = username
        return MeOut(username=username)

    @app.post("/api/auth/login", response_model=MeOut)
    def auth_login(payload: LoginRequest, request: Request, conn=Depends(get_db)):
        row = db.get_user_by_username(conn, payload.username.strip())
        if row is None or not auth.verify_password(payload.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        request.session["user_id"] = row["id"]
        request.session["username"] = row["username"]
        return MeOut(username=row["username"])

    @app.post("/api/auth/logout")
    def auth_logout(request: Request):
        request.session.clear()
        return {"ok": True}

    @app.get("/api/auth/me", response_model=MeOut)
    def auth_me(request: Request):
        if not request.session.get("user_id"):
            raise HTTPException(status_code=401, detail="Not authenticated")
        return MeOut(username=request.session.get("username", ""))

    # Serves the built SolidJS SPA (frontend/dist) in production, so a single
    # container/process handles both the API and the UI. Registered last so
    # it never shadows /api/* or /library/*: unmatched routes reach here and
    # get index.html, letting solid-router's client-side routes (e.g.
    # /comic/5) resolve correctly on a hard refresh. Absent in local dev,
    # where the Vite dev server serves the frontend instead (see vite.config.ts).
    if frontend_dist is not None and frontend_dist.is_dir():
        assets_dir = frontend_dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

        @app.get("/{full_path:path}")
        def serve_frontend(full_path: str):
            candidate = frontend_dist / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(frontend_dist / "index.html")

    return app


# Read at import time so `uvicorn backend.main:app` (the Docker CMD - see
# Dockerfile/Makefile) picks up paths without going through main()'s argparse,
# which never runs on that invocation. FRONTEND_DIST is unset in local dev
# (Vite serves the frontend instead) and set to the built dist/ in the image.
app = create_app(
    Path(os.environ.get("DB_PATH", "catalog.db")),
    Path(os.environ.get("LIBRARY_DIR", "library")),
    Path(os.environ.get("IMPORT_DIR", "import")),
    Path(os.environ["FRONTEND_DIST"]) if os.environ.get("FRONTEND_DIST") else None,
)


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Run the comic catalog API server.")
    parser.add_argument("--db-path", type=Path, default=Path(os.environ.get("DB_PATH", "catalog.db")))
    parser.add_argument(
        "--library-dir", type=Path, default=Path(os.environ.get("LIBRARY_DIR", "library"))
    )
    parser.add_argument(
        "--import-dir", type=Path, default=Path(os.environ.get("IMPORT_DIR", "import"))
    )
    parser.add_argument(
        "--frontend-dist",
        type=Path,
        default=Path(os.environ["FRONTEND_DIST"]) if os.environ.get("FRONTEND_DIST") else None,
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    args = parser.parse_args()

    global app
    app = create_app(args.db_path, args.library_dir, args.import_dir, args.frontend_dist)

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
