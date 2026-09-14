import shutil
import subprocess
from pathlib import Path

from . import config
from .errors import ImageMagickNotFoundError, ImageProcessingError

_TIMEOUT_SECONDS = 120


def _magick_binary() -> str:
    if shutil.which("magick"):
        return "magick"
    if shutil.which("convert"):
        return "convert"
    raise ImageMagickNotFoundError(
        "ImageMagick was not found on PATH (looked for `magick` and `convert`). "
        "Install it first, e.g. `apt install imagemagick` or `brew install imagemagick`, "
        "then re-run this importer."
    )


def check_imagemagick_available() -> None:
    _magick_binary()


def _run(args: list[str]) -> None:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ImageProcessingError(f"ImageMagick timed out: {' '.join(args)}") from exc
    if result.returncode != 0:
        raise ImageProcessingError(
            f"ImageMagick command failed ({result.returncode}): {' '.join(args)}\n{result.stderr.strip()}"
        )


def make_thumbnail(src_path: Path, thumb_path: Path) -> None:
    binary = _magick_binary()
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    thumb_args = [
        binary,
        str(src_path),
        "-resize", f"{config.THUMB_MAX_DIMENSION}x{config.THUMB_MAX_DIMENSION}>",
        "-strip",
        "-quality", str(config.THUMB_JPEG_QUALITY),
        str(thumb_path),
    ]
    _run(thumb_args)


def process_image_with_imagemagick(src_path: Path, optimized_path: Path, thumb_path: Path) -> None:
    binary = _magick_binary()

    optimized_path.parent.mkdir(parents=True, exist_ok=True)

    # No -trim/-deskew here: ImageMagick's heuristics can't reliably find a comic's
    # edges against an arbitrary photo background. Cropping/straightening is instead
    # suggested by Claude (comics_importer.vision) from the full frame below, and
    # applied precisely by the user via the frontend crop editor.
    full_args = [
        binary,
        str(src_path),
        "-auto-orient",
        "-resize", f"{config.FULL_MAX_DIMENSION}x{config.FULL_MAX_DIMENSION}>",
        "-strip",
        "-interlace", "Plane",
        "-sampling-factor", "4:2:0",
        "-quality", str(config.FULL_JPEG_QUALITY),
        str(optimized_path),
    ]
    _run(full_args)

    make_thumbnail(optimized_path, thumb_path)
