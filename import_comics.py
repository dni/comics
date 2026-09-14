#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from comics_importer.config import CLAUDE_MODEL
from comics_importer.errors import ImageMagickNotFoundError
from comics_importer.pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Import, catalog, and organize scanned comic books.")
    parser.add_argument("--import-dir", type=Path, default=Path("import"))
    parser.add_argument("--library-dir", type=Path, default=Path("library"))
    parser.add_argument("--db-path", type=Path, default=Path("catalog.db"))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover files and report what would happen; no ImageMagick, no API calls, "
        "no DB writes, no file moves.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Process at most N files.")
    parser.add_argument("--model", default=CLAUDE_MODEL)
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    try:
        stats = run_pipeline(
            args.import_dir,
            args.library_dir,
            args.db_path,
            dry_run=args.dry_run,
            limit=args.limit,
            model=args.model,
        )
    except ImageMagickNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None

    if args.dry_run:
        print(f"Would process: {stats.would_process}")
    else:
        print(f"Processed: {stats.processed}  Skipped (already imported): {stats.skipped}  Failed: {stats.failed}")


if __name__ == "__main__":
    main()
