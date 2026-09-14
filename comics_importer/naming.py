import re
from pathlib import Path

_UNSAFE_CHARS = re.compile(r'[\\/:*?"<>|]')
_WHITESPACE = re.compile(r"\s+")


def sanitize_component(value: str | None) -> str:
    if not value:
        return "Unknown"
    cleaned = _UNSAFE_CHARS.sub("_", value)
    cleaned = _WHITESPACE.sub(" ", cleaned).strip()
    return cleaned or "Unknown"


def dedupe_path(path: Path, ignore_path: Path | None = None) -> Path:
    def _exists(p: Path) -> bool:
        if ignore_path is not None and p.resolve() == ignore_path.resolve():
            return False
        return p.exists()

    if not _exists(path):
        return path
    stem, suffix, parent = path.stem, path.suffix, path.parent
    n = 2
    while True:
        candidate = parent / f"{stem} ({n}){suffix}"
        if not _exists(candidate):
            return candidate
        n += 1


def build_library_path(
    series: str | None,
    issue_number: str | None,
    year: int | None,
    library_dir: Path,
    ignore_path: Path | None = None,
) -> Path:
    series_name = sanitize_component(series) if series else "Unknown Series"
    issue_label = sanitize_component(issue_number) if issue_number else "Unknown"

    filename = f"{series_name} #{issue_label}"
    if year:
        filename += f" ({year})"
    filename += ".jpg"

    path = library_dir / series_name / filename
    return dedupe_path(path, ignore_path=ignore_path)
