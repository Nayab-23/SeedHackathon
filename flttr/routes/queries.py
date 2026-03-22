import math
from fastapi import APIRouter
from flttr.database import get_connection

router = APIRouter(prefix="/api/queries", tags=["queries"])

db_path: str = ""


@router.get("")
def get_queries(
    action: str = "",
    search: str = "",
    page: int = 1,
    per_page: int = 100,
):
    conn = get_connection(db_path)

    conditions = []
    params = []

    if action:
        conditions.append("action = ?")
        params.append(action.upper())

    if search:
        conditions.append("domain LIKE ?")
        params.append(f"%{search}%")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    total = conn.execute(f"SELECT COUNT(*) FROM query_log {where}", params).fetchone()[0]
    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT id, client_ip, domain, query_type, action, response_ms, logged_at FROM query_log {where} ORDER BY logged_at DESC LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()
    conn.close()

    return {
        "queries": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "pages": math.ceil(total / per_page) if total > 0 else 1,
    }
