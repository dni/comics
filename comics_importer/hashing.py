import hashlib
from pathlib import Path

_CHUNK_SIZE = 1024 * 1024


def compute_content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
