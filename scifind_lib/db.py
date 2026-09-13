"""SQLite connection, schema bootstrap, low-level helpers."""

import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger("scifind.db")

DEFAULT_DATABASE_PATH = str(Path(__file__).resolve().parent.parent / "scifind.db")


def database_path():
    return os.environ.get("SCIFIND_DB", DEFAULT_DATABASE_PATH)


def sql_literal(value):
    """Render a Python value as a SQL literal string; for SQL *files* only, never live queries."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def insert_statement(table, columns, values):
    """One INSERT OR IGNORE statement for `values` (a parallel list to `columns`)."""
    vals = ", ".join(sql_literal(v) for v in values)
    return f"INSERT OR IGNORE INTO {table} ({', '.join(columns)}) VALUES ({vals});"


def in_clause(ids):
    """Build a `(?, ?, …)` placeholder list + values; empty input yields ``("NULL", ())``."""
    items = list(ids)
    return ("NULL", ()) if not items else (",".join("?" for _ in items), tuple(items))


def open_database():
    path = database_path()
    if parent := os.path.dirname(path):
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    for pragma in ("foreign_keys = ON", "journal_mode = WAL", "busy_timeout = 5000", "synchronous = NORMAL"):
        conn.execute(f"PRAGMA {pragma}")
    return conn


@contextmanager
def database_connection():
    """Yield an open DB connection, always closing it afterwards."""
    conn = open_database()
    try:
        yield conn
    finally:
        conn.close()


def database_has_formula_table(conn):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='formula'").fetchone())


# Keyed by (db_path, mtime_ns, size) so reseed invalidates; :memory:/URI bypass.
_PROCESS_CACHE: dict = {}


def db_cache_key():
    """(path, mtime_ns, size) for the current DB file, or None if uncacheable."""
    path = database_path()
    if not path or path == ":memory:" or path.startswith("file:"):
        return None
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (path, st.st_mtime_ns, st.st_size)


def cached_process(key_name, loader):
    """Cached loader() for (db_cache_key, key_name); shared — copy mutables before mutating."""
    ckey = db_cache_key()
    if ckey is None:
        return loader()
    full = (ckey, key_name)
    if full not in _PROCESS_CACHE:
        _PROCESS_CACHE[full] = loader()
    return _PROCESS_CACHE[full]


def process_cached(key_name):
    """Decorator for uncached ``fn(conn, ...)`` loaders using the process cache."""
    from functools import wraps

    def _decorator(fn):
        @wraps(fn)
        def _wrapper(conn, *args, **kwargs):
            key = key_name if not args and not kwargs else f"{key_name}:{args!r}:{sorted(kwargs.items())!r}"
            return cached_process(key, lambda: fn(conn, *args, **kwargs))
        _wrapper.uncached = fn
        return _wrapper
    return _decorator


def clear_process_cache():
    """Drop all process-cached reference data."""
    _PROCESS_CACHE.clear()


def initialize_database(force=False, schema_path=None, seed_path=None):
    """Create (or recreate) the schema and seed data; ``force`` requires SCIFIND_ALLOW_FORCE_INIT=1."""
    if force and os.environ.get("SCIFIND_ALLOW_FORCE_INIT", "").lower() not in {"1", "true", "yes"}:
        raise PermissionError("initialize_database(force=True) requires SCIFIND_ALLOW_FORCE_INIT=1")
    project_dir = Path(__file__).resolve().parent.parent
    schema_path = schema_path or project_dir / "schema.sql"
    seed_path = seed_path or project_dir / "seed.sql"
    tables = ("formula_relation", "formula_token", "formula", "operator", "constant",
              "compound_unit", "unit", "quantity", "topic", "si_prefix",
              "slug_override", "dimension_filter_operator", "app_config")
    with database_connection() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            if force:
                for table in tables:
                    conn.execute(f"DROP TABLE IF EXISTS {table}")
            for path in (schema_path, seed_path):
                conn.executescript(Path(path).read_text(encoding="utf-8"))
            conn.execute("PRAGMA foreign_keys = ON")
            conn.commit()
        except Exception as exc:
            logger.error("initialize_database failed; rolling back: %s", exc)
            conn.rollback()
            raise
        clear_process_cache()
        return conn.total_changes