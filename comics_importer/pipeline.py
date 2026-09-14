import shutil
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import config, db
from .errors import ImageProcessingError, VisionAPIError
from .hashing import compute_content_hash
from .imagemagick import check_imagemagick_available, process_image_with_imagemagick
from .naming import build_library_path
from .vision import identify_metadata


@dataclass
class PipelineStats:
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    would_process: int = 0


def discover_import_files(import_dir: Path) -> list[Path]:
    if not import_dir.is_dir():
        return []
    failed_dir = import_dir / "failed"
    files = [
        p
        for p in import_dir.iterdir()
        if p.is_file()
        and p.suffix.lower() in config.SUPPORTED_EXTENSIONS
        and failed_dir not in p.parents
    ]
    return sorted(files)


def move_to_failed(src_path: Path, import_dir: Path) -> Path:
    failed_dir = import_dir / "failed"
    failed_dir.mkdir(parents=True, exist_ok=True)
    dest = failed_dir / src_path.name
    shutil.move(str(src_path), str(dest))
    return dest


def process_one(
    src_path: Path,
    *,
    import_dir: Path,
    library_dir: Path,
    conn: sqlite3.Connection,
    client,
    dry_run: bool,
    model: str = config.CLAUDE_MODEL,
) -> str:
    content_hash = compute_content_hash(src_path)
    existing = db.find_by_hash(conn, content_hash)

    if existing is not None and existing["status"] == "processed" and not dry_run:
        return "skipped"

    if dry_run:
        status = "already imported" if existing and existing["status"] == "processed" else "new"
        print(f"[dry-run] {src_path.name}: {status} (hash {content_hash[:12]}...)")
        return "would_process"

    with tempfile.TemporaryDirectory() as work_dir:
        work_path = Path(work_dir)
        optimized_tmp = work_path / "optimized.jpg"
        thumb_tmp = work_path / "thumb.jpg"

        process_image_with_imagemagick(src_path, optimized_tmp, thumb_tmp)
        metadata, raw_json = identify_metadata(thumb_tmp, client, model=model)

        dest_path = build_library_path(
            metadata.get("series"), metadata.get("issue_number"), metadata.get("year"), library_dir
        )
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(optimized_tmp), str(dest_path))

    db.upsert_comic(
        conn,
        content_hash=content_hash,
        original_filename=src_path.name,
        original_path=str(src_path),
        series=metadata.get("series"),
        issue_number=metadata.get("issue_number"),
        year=metadata.get("year"),
        publisher=metadata.get("publisher"),
        language=metadata.get("language"),
        condition_grade=metadata.get("condition_grade"),
        numeric_grade=metadata.get("numeric_grade"),
        confidence=metadata.get("confidence"),
        notes=metadata.get("notes"),
        suggested_rotation_degrees=metadata.get("rotation_degrees"),
        suggested_crop_left=metadata.get("crop_left"),
        suggested_crop_top=metadata.get("crop_top"),
        suggested_crop_width=metadata.get("crop_width"),
        suggested_crop_height=metadata.get("crop_height"),
        optimized_image_path=str(dest_path),
        claude_raw_response=raw_json,
        status="processed",
        error_message=None,
    )

    src_path.unlink()
    return "processed"


def _record_failure(src_path: Path, import_dir: Path, conn: sqlite3.Connection, exc: Exception) -> None:
    print(f"FAILED {src_path.name}: {exc}", file=sys.stderr)
    content_hash = compute_content_hash(src_path)
    failed_path = move_to_failed(src_path, import_dir)
    db.upsert_comic(
        conn,
        content_hash=content_hash,
        original_filename=src_path.name,
        original_path=str(failed_path),
        status="failed",
        error_message=str(exc),
    )


def process_and_record(
    src_path: Path,
    *,
    import_dir: Path,
    library_dir: Path,
    conn: sqlite3.Connection,
    client,
    dry_run: bool = False,
    model: str = config.CLAUDE_MODEL,
) -> tuple[str, Exception | None]:
    """Run process_one and, on failure, move the file to import/failed/ and record it.

    Returns (result, error) where result is one of "processed", "skipped",
    "would_process", or "failed". One bad file must never raise past this point —
    callers (CLI batch loop, API upload endpoint) rely on that to keep going.
    """
    try:
        result = process_one(
            src_path,
            import_dir=import_dir,
            library_dir=library_dir,
            conn=conn,
            client=client,
            dry_run=dry_run,
            model=model,
        )
        return result, None
    except (ImageProcessingError, VisionAPIError) as exc:
        _record_failure(src_path, import_dir, conn, exc)
        return "failed", exc
    except Exception as exc:  # noqa: BLE001 - one bad file must never abort the batch
        _record_failure(src_path, import_dir, conn, exc)
        return "failed", exc


def run_pipeline(
    import_dir: Path,
    library_dir: Path,
    db_path: Path,
    *,
    dry_run: bool = False,
    limit: int | None = None,
    model: str = config.CLAUDE_MODEL,
) -> PipelineStats:
    stats = PipelineStats()

    if not dry_run:
        check_imagemagick_available()

    client = None
    if not dry_run:
        import anthropic

        client = anthropic.Anthropic()

    conn = db.get_connection(db_path)
    db.init_db(conn)

    files = discover_import_files(import_dir)
    if limit is not None:
        files = files[:limit]

    for src_path in files:
        result, _ = process_and_record(
            src_path,
            import_dir=import_dir,
            library_dir=library_dir,
            conn=conn,
            client=client,
            dry_run=dry_run,
        )

        if result == "processed":
            stats.processed += 1
        elif result == "skipped":
            stats.skipped += 1
        elif result == "would_process":
            stats.would_process += 1
        elif result == "failed":
            stats.failed += 1

    conn.close()
    return stats
