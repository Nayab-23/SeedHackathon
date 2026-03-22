import os
from fastapi import APIRouter
from flttr.database import get_connection

router = APIRouter(prefix="/api/system", tags=["system"])

db_path: str = ""


@router.get("/health")
def health():
    conn = get_connection(db_path)
    query_count = conn.execute("SELECT COUNT(*) FROM query_log").fetchone()[0]
    blacklist_count = conn.execute("SELECT COUNT(*) FROM domain_lists").fetchone()[0]
    conn.close()

    db_size = 0
    if os.path.exists(db_path):
        db_size = round(os.path.getsize(db_path) / (1024 * 1024), 2)

    return {
        "dns_server": "running",
        "database_size_mb": db_size,
        "query_log_rows": query_count,
        "blacklist_count": blacklist_count,
    }
