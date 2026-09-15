import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS comics (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash           TEXT NOT NULL UNIQUE,
    original_filename      TEXT NOT NULL,
    original_path          TEXT NOT NULL,
    series                 TEXT,
    issue_number           TEXT,
    year                   INTEGER,
    publisher              TEXT,
    language                TEXT,
    condition_grade        TEXT,
    numeric_grade           REAL,
    confidence              TEXT,
    notes                  TEXT,
    storage_location       TEXT,
    suggested_rotation_degrees REAL,
    suggested_crop_left        REAL,
    suggested_crop_top         REAL,
    suggested_crop_width       REAL,
    suggested_crop_height      REAL,
    for_sale               INTEGER NOT NULL DEFAULT 0,
    asking_price           REAL,
    ebay_listing_url       TEXT,
    ebay_listing_status    TEXT,
    optimized_image_path   TEXT,
    thumbnail_image_path   TEXT,
    claude_raw_response    TEXT,
    status                 TEXT NOT NULL DEFAULT 'pending',
    error_message          TEXT,
    imported_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_comics_series ON comics(series);
CREATE INDEX IF NOT EXISTS idx_comics_status ON comics(status);

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS app_settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);
"""

_UPSERT = """
INSERT INTO comics (content_hash, original_filename, original_path, series, issue_number, year,
                     publisher, language, condition_grade, numeric_grade, confidence, notes,
                     storage_location,
                     suggested_rotation_degrees, suggested_crop_left, suggested_crop_top,
                     suggested_crop_width, suggested_crop_height,
                     optimized_image_path, thumbnail_image_path, claude_raw_response,
                     status, error_message, updated_at)
VALUES (:content_hash, :original_filename, :original_path, :series, :issue_number, :year,
        :publisher, :language, :condition_grade, :numeric_grade, :confidence, :notes,
        :storage_location,
        :suggested_rotation_degrees, :suggested_crop_left, :suggested_crop_top,
        :suggested_crop_width, :suggested_crop_height,
        :optimized_image_path, :thumbnail_image_path, :claude_raw_response,
        :status, :error_message, strftime('%Y-%m-%dT%H:%M:%fZ','now'))
ON CONFLICT(content_hash) DO UPDATE SET
    series=excluded.series, issue_number=excluded.issue_number, year=excluded.year,
    publisher=excluded.publisher, language=excluded.language, condition_grade=excluded.condition_grade,
    numeric_grade=excluded.numeric_grade,
    confidence=excluded.confidence, notes=excluded.notes,
    suggested_rotation_degrees=excluded.suggested_rotation_degrees,
    suggested_crop_left=excluded.suggested_crop_left, suggested_crop_top=excluded.suggested_crop_top,
    suggested_crop_width=excluded.suggested_crop_width, suggested_crop_height=excluded.suggested_crop_height,
    optimized_image_path=excluded.optimized_image_path, thumbnail_image_path=excluded.thumbnail_image_path,
    claude_raw_response=excluded.claude_raw_response, status=excluded.status,
    error_message=excluded.error_message, updated_at=excluded.updated_at
"""
# storage_location is deliberately excluded from DO UPDATE SET above: it's
# user-managed and must survive a re-import/retry of the same photo hash.


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
    _migrate(conn)


_MIGRATION_COLUMNS = {
    "storage_location": "TEXT",
    "numeric_grade": "REAL",
    "suggested_rotation_degrees": "REAL",
    "suggested_crop_left": "REAL",
    "suggested_crop_top": "REAL",
    "suggested_crop_width": "REAL",
    "suggested_crop_height": "REAL",
    "for_sale": "INTEGER NOT NULL DEFAULT 0",
    "asking_price": "REAL",
    "ebay_listing_url": "TEXT",
    "ebay_listing_status": "TEXT",
}


def _migrate(conn: sqlite3.Connection) -> None:
    existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(comics)")}
    changed = False
    for column, sql_type in _MIGRATION_COLUMNS.items():
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE comics ADD COLUMN {column} {sql_type}")
            changed = True
    if changed:
        conn.commit()
    # Created here (not in SCHEMA) since the for_sale column may only exist after
    # the ALTER TABLE above runs on a pre-existing database.
    conn.execute("CREATE INDEX IF NOT EXISTS idx_comics_for_sale ON comics(for_sale)")
    conn.commit()


def find_by_hash(conn: sqlite3.Connection, content_hash: str) -> sqlite3.Row | None:
    cur = conn.execute("SELECT * FROM comics WHERE content_hash = ?", (content_hash,))
    return cur.fetchone()


_SORT_COLUMNS = {"series", "issue_number", "year", "confidence", "imported_at", "updated_at"}

_EDITABLE_FIELDS = {
    "series",
    "issue_number",
    "year",
    "publisher",
    "language",
    "condition_grade",
    "numeric_grade",
    "confidence",
    "notes",
    "storage_location",
    "for_sale",
    "asking_price",
    "ebay_listing_url",
    "ebay_listing_status",
    # not exposed on the public ComicUpdate model - only ever set internally,
    # by the import pipeline and the reclassify endpoint
    "suggested_rotation_degrees",
    "suggested_crop_left",
    "suggested_crop_top",
    "suggested_crop_width",
    "suggested_crop_height",
    "claude_raw_response",
    "optimized_image_path",
}


def list_for_sale_comics(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM comics WHERE status = 'processed' AND for_sale = 1 ORDER BY series ASC, id ASC"
    ).fetchall()


_CONFIDENCE_VALUES = {"high", "medium", "low"}


def list_comics(
    conn: sqlite3.Connection,
    *,
    q: str | None = None,
    sort_by: str = "series",
    order: str = "asc",
    status: str = "processed",
    confidence: str | None = None,
) -> list[sqlite3.Row]:
    if sort_by not in _SORT_COLUMNS:
        sort_by = "series"
    order_sql = "DESC" if order == "desc" else "ASC"

    clauses = ["status = :status"]
    params: dict = {"status": status}
    if q:
        clauses.append(
            "(series LIKE :q OR issue_number LIKE :q OR publisher LIKE :q OR storage_location LIKE :q)"
        )
        params["q"] = f"%{q}%"
    if confidence and confidence in _CONFIDENCE_VALUES:
        clauses.append("confidence = :confidence")
        params["confidence"] = confidence

    sql = f"SELECT * FROM comics WHERE {' AND '.join(clauses)} ORDER BY {sort_by} {order_sql}, id ASC"
    return conn.execute(sql, params).fetchall()


def list_failed_comics(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM comics WHERE status = 'failed' ORDER BY updated_at DESC"
    ).fetchall()


def find_duplicate_candidates(
    conn: sqlite3.Connection,
    comic_id: int,
    series: str | None,
    issue_number: str | None,
) -> list[sqlite3.Row]:
    if not series or not issue_number:
        return []
    return conn.execute(
        "SELECT id, series, issue_number, year, publisher, condition_grade, numeric_grade FROM comics "
        "WHERE status = 'processed' AND id != :id "
        "AND lower(series) = lower(:series) AND lower(issue_number) = lower(:issue_number)",
        {"id": comic_id, "series": series, "issue_number": issue_number},
    ).fetchall()


def list_series_issues(
    conn: sqlite3.Connection,
    comic_id: int,
    series: str | None,
) -> list[sqlite3.Row]:
    """Other processed comics in the same series, for cross-issue navigation on the detail page."""
    if not series:
        return []
    return conn.execute(
        "SELECT id, issue_number, year, optimized_image_path, updated_at FROM comics "
        "WHERE status = 'processed' AND id != :id AND lower(series) = lower(:series) "
        "ORDER BY CAST(issue_number AS INTEGER) ASC, issue_number ASC",
        {"id": comic_id, "series": series},
    ).fetchall()


def list_all_comics_for_export(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM comics WHERE status = 'processed' ORDER BY series ASC, issue_number ASC"
    ).fetchall()


def get_comic(conn: sqlite3.Connection, comic_id: int) -> sqlite3.Row | None:
    cur = conn.execute("SELECT * FROM comics WHERE id = ?", (comic_id,))
    return cur.fetchone()


def delete_comic(conn: sqlite3.Connection, comic_id: int) -> None:
    conn.execute("DELETE FROM comics WHERE id = ?", (comic_id,))
    conn.commit()


def update_comic_fields(conn: sqlite3.Connection, comic_id: int, **fields) -> None:
    fields = {k: v for k, v in fields.items() if k in _EDITABLE_FIELDS}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    fields["id"] = comic_id
    conn.execute(
        f"UPDATE comics SET {set_clause}, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = :id",
        fields,
    )
    conn.commit()


def upsert_comic(conn: sqlite3.Connection, **fields) -> int:
    defaults = {
        "series": None,
        "issue_number": None,
        "year": None,
        "publisher": None,
        "language": None,
        "condition_grade": None,
        "numeric_grade": None,
        "confidence": None,
        "notes": None,
        "storage_location": None,
        "suggested_rotation_degrees": None,
        "suggested_crop_left": None,
        "suggested_crop_top": None,
        "suggested_crop_width": None,
        "suggested_crop_height": None,
        "optimized_image_path": None,
        "thumbnail_image_path": None,
        "claude_raw_response": None,
        "status": "pending",
        "error_message": None,
    }
    defaults.update(fields)
    conn.execute(_UPSERT, defaults)
    conn.commit()
    row = find_by_hash(conn, fields["content_hash"])
    return row["id"]


def count_users(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]


def get_user_by_username(conn: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def create_user(conn: sqlite3.Connection, username: str, password_hash: str) -> int:
    cur = conn.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash)
    )
    conn.commit()
    return cur.lastrowid


def get_setting(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO app_settings (key, value) VALUES (:key, :value) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        {"key": key, "value": value},
    )
    conn.commit()
