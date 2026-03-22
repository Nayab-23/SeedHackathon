import sqlite3
import os


SCHEMA = """
CREATE TABLE IF NOT EXISTS domain_lists (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    domain      TEXT NOT NULL UNIQUE,
    added_by    TEXT DEFAULT 'manual',
    reason      TEXT,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_domain_lists_domain ON domain_lists(domain);

CREATE TABLE IF NOT EXISTS query_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_ip   TEXT NOT NULL,
    domain      TEXT NOT NULL,
    query_type  TEXT,
    action      TEXT NOT NULL,
    response_ms REAL,
    logged_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_query_log_time ON query_log(logged_at);
CREATE INDEX IF NOT EXISTS idx_query_log_action ON query_log(action);
CREATE INDEX IF NOT EXISTS idx_query_log_domain ON query_log(domain);
"""


def init_db(db_path: str):
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn
