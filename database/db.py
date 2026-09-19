"""
Database connection manager and schema initialization with SQLite WAL mode.
"""
import sqlite3
import threading
from pathlib import Path
from contextlib import contextmanager
from typing import Generator
from config.settings import DB_PATH

_local = threading.local()

def get_connection() -> sqlite3.Connection:
    """Get thread-local SQLite connection with WAL mode and row factory."""
    if not hasattr(_local, "connection") or _local.connection is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(DB_PATH),
            timeout=30.0,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        # Enable WAL (Write-Ahead Logging) for high-performance concurrent reads and writes
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        _local.connection = conn
    return _local.connection

@contextmanager
def get_db_cursor() -> Generator[sqlite3.Cursor, None, None]:
    """Context manager for executing queries with automatic commit/rollback."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()

def init_db():
    """Execute schema.sql to initialize all tables and indexes."""
    schema_path = Path(__file__).resolve().parent / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = get_connection()
    conn.executescript(schema_sql)
    conn.commit()
