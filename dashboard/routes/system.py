"""System health check endpoint."""

import os
import time
from fastapi import APIRouter

from dashboard.database import get_db, get_db_path

router = APIRouter(prefix="/api/system", tags=["system"])

_start_time = time.time()


@router.get("/health")
def health_check():
    db = get_db()
    db_path = get_db_path()

    # Database size
    try:
        db_size_mb = round(os.path.getsize(db_path) / (1024 * 1024), 1)
    except OSError:
        db_size_mb = 0

    # Query log rows
    query_log_rows = db.execute("SELECT COUNT(*) FROM query_log").fetchone()[0]

    # Active profiles
    active_profiles = db.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]

    # Active focus sessions
    active_focus = db.execute(
        "SELECT COUNT(*) FROM focus_notes "
        "WHERE ended_early = 0 AND expires_at > datetime('now') AND starts_at <= datetime('now')"
    ).fetchone()[0]

    # List counts
    blacklist_count = db.execute(
        "SELECT COUNT(*) FROM domain_lists WHERE list_type = 'blacklist'"
    ).fetchone()[0]
    whitelist_count = db.execute(
        "SELECT COUNT(*) FROM domain_lists WHERE list_type = 'whitelist'"
    ).fetchone()[0]

    return {
        "dns_server": "running",
        "database_size_mb": db_size_mb,
        "query_log_rows": query_log_rows,
        "uptime_seconds": int(time.time() - _start_time),
        "active_profiles": active_profiles,
        "active_focus_sessions": active_focus,
        "blacklist_count": blacklist_count,
        "whitelist_count": whitelist_count,
    }
