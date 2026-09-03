"""SQLite connection, schema bootstrap, low-level helpers."""

import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger("scifind.db")

DEFAULT_DATABASE_PATH = str(Path(__file__).resolve().parent.parent / "scifind.db")


def database_path():
    return os.environ.get("SCIFIND_DB", DEFAULT_DATABASE_PATH)


def sql_literal(value):
    """Render a Python value as a SQL literal string (single quotes doubled)."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def in_clause(ids):
    """Build a `(?, ?, …)` placeholder list for an IN clause + the tuple of values."""
    return ",".join("?" for _ in ids), tuple(ids)


def open_database():
    path = database_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def database_has_formula_table(conn):
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='formula'"
    ).fetchone())


def initialize_database(force=False, schema_path=None, seed_path=None):
    """Create (or recreate) the schema and seed data.

    Foreign keys are disabled during the seed load so the seed file
    doesn't have to be ordered around referential integrity.

    ``force=True`` drops every table and reloads schema + seed. It requires
    ``SCIFIND_ALLOW_FORCE_INIT=1`` so a stray web request can't wipe the DB.
    """
    if force and os.environ.get("SCIFIND_ALLOW_FORCE_INIT", "").lower() not in (
        "1", "true", "yes",
    ):
        raise PermissionError(
            "initialize_database(force=True) requires SCIFIND_ALLOW_FORCE_INIT=1"
        )
    project_dir = Path(__file__).resolve().parent.parent
    schema_path = schema_path or (project_dir / "schema.sql")
    seed_path = seed_path or (project_dir / "seed.sql")
    conn = open_database()
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            if force:
                for table in (
                    "formula_relation", "formula_token",
                    "formula", "operator", "constant",
                    "compound_unit", "unit", "quantity",
                    "si_prefix",
                ):
                    conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.executescript(Path(schema_path).read_text(encoding="utf-8"))
            conn.executescript(Path(seed_path).read_text(encoding="utf-8"))
            conn.execute("PRAGMA foreign_keys = ON")
            conn.commit()
        except Exception as exc:
            logger.error("initialize_database failed; rolling back: %s", exc)
            conn.execute("ROLLBACK")
            raise
        return conn.total_changes
    finally:
        conn.close()