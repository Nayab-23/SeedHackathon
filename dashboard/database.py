"""SQLite database connection, schema initialization, and helper functions."""

import sqlite3
import os
import threading

_db_path: str = ""
_local = threading.local()


def set_db_path(path: str):
    """Set the global database path."""
    global _db_path
    _db_path = path


def get_db_path() -> str:
    """Return the configured database path."""
    return _db_path


def get_db() -> sqlite3.Connection:
    """Get a thread-local SQLite connection with row factory enabled."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(_db_path, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def init_db(db_path: str):
    """Initialize the database: create tables and indices if they don't exist."""
    set_db_path(db_path)
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        -- PROFILES: people on the network
        CREATE TABLE IF NOT EXISTS profiles (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- DEVICES: Tailscale IPs assigned to a profile
        CREATE TABLE IF NOT EXISTS devices (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id  TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
            ip          TEXT NOT NULL UNIQUE,
            label       TEXT,
            added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- FOCUS NOTES: what someone should be doing, with expiry
        CREATE TABLE IF NOT EXISTS focus_notes (
            id          TEXT PRIMARY KEY,
            profile_id  TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
            note        TEXT NOT NULL,
            strictness  TEXT DEFAULT 'moderate',
            starts_at   TIMESTAMP NOT NULL,
            expires_at  TIMESTAMP NOT NULL,
            ended_early BOOLEAN DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- DOMAIN LISTS: blacklist and whitelist with metadata
        CREATE TABLE IF NOT EXISTS domain_lists (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            domain      TEXT NOT NULL,
            list_type   TEXT NOT NULL CHECK(list_type IN ('blacklist', 'whitelist')),
            added_by    TEXT DEFAULT 'manual',
            reason      TEXT,
            added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(domain, list_type)
        );

        -- QUERY LOG: every DNS query that passes through the server
        CREATE TABLE IF NOT EXISTS query_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            client_ip   TEXT NOT NULL,
            profile_id  TEXT,
            domain      TEXT NOT NULL,
            query_type  TEXT,
            action      TEXT NOT NULL,
            response_ms REAL,
            logged_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- ANALYSIS LOG: results from the LangChain agent's analysis
        CREATE TABLE IF NOT EXISTS analysis_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            domain      TEXT NOT NULL,
            profile_id  TEXT,
            risk_level  TEXT,
            category    TEXT,
            reasoning   TEXT,
            action_taken TEXT,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Create indices (IF NOT EXISTS for idempotency)
    indices = [
        "CREATE INDEX IF NOT EXISTS idx_focus_active ON focus_notes(profile_id, expires_at)",
        "CREATE INDEX IF NOT EXISTS idx_domain_lists_type ON domain_lists(list_type)",
        "CREATE INDEX IF NOT EXISTS idx_domain_lists_domain ON domain_lists(domain)",
        "CREATE INDEX IF NOT EXISTS idx_query_log_time ON query_log(logged_at)",
        "CREATE INDEX IF NOT EXISTS idx_query_log_profile ON query_log(profile_id)",
        "CREATE INDEX IF NOT EXISTS idx_query_log_action ON query_log(action)",
        "CREATE INDEX IF NOT EXISTS idx_query_log_domain ON query_log(domain)",
        "CREATE INDEX IF NOT EXISTS idx_analysis_log_risk ON analysis_log(risk_level)",
        "CREATE INDEX IF NOT EXISTS idx_analysis_log_domain ON analysis_log(domain)",
    ]
    for idx in indices:
        conn.execute(idx)

    conn.commit()
    conn.close()


def cleanup_old_queries(db_path: str = None):
    """Delete query_log rows older than 7 days."""
    path = db_path or _db_path
    conn = sqlite3.connect(path)
    conn.execute("DELETE FROM query_log WHERE logged_at < datetime('now', '-7 days')")
    conn.commit()
    conn.close()
