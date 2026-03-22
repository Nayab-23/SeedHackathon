"""Query log routes: paginated listing with filters and CSV export."""

import csv
import io
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from typing import Optional

from dashboard.database import get_db

router = APIRouter(prefix="/api/queries", tags=["queries"])


def _build_query_filters(
    profile_id: Optional[str],
    action: Optional[str],
    search: Optional[str],
    from_time: Optional[str],
    to_time: Optional[str],
):
    """Build WHERE clause and params for query log filtering."""
    where_clauses = []
    params = []

    if profile_id:
        where_clauses.append("q.profile_id = ?")
        params.append(profile_id)

    if action:
        where_clauses.append("q.action = ?")
        params.append(action.upper())

    if search:
        where_clauses.append("q.domain LIKE ?")
        params.append(f"%{search}%")

    if from_time:
        where_clauses.append("q.logged_at >= ?")
        params.append(from_time)

    if to_time:
        where_clauses.append("q.logged_at <= ?")
        params.append(to_time)

    where = ""
    if where_clauses:
        where = "WHERE " + " AND ".join(where_clauses)

    return where, params


@router.get("")
def get_queries(
    profile_id: Optional[str] = None,
    action: Optional[str] = None,
    search: Optional[str] = None,
    from_time: Optional[str] = Query(None, alias="from"),
    to_time: Optional[str] = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=1000),
    
):
    db = get_db()
    where, params = _build_query_filters(profile_id, action, search, from_time, to_time)

    # Total count
    total = db.execute(
        f"SELECT COUNT(*) FROM query_log q {where}", params
    ).fetchone()[0]

    # Paginated results with profile name join
    offset = (page - 1) * per_page
    rows = db.execute(
        f"SELECT q.id, q.client_ip, p.name as profile_name, q.domain, q.query_type, "
        f"q.action, q.response_ms, q.logged_at "
        f"FROM query_log q LEFT JOIN profiles p ON q.profile_id = p.id "
        f"{where} ORDER BY q.logged_at DESC LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()

    pages = max(1, (total + per_page - 1) // per_page)

    return {
        "queries": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get("/export")
def export_queries(
    profile_id: Optional[str] = None,
    action: Optional[str] = None,
    search: Optional[str] = None,
    from_time: Optional[str] = Query(None, alias="from"),
    to_time: Optional[str] = Query(None, alias="to"),
    
):
    db = get_db()
    where, params = _build_query_filters(profile_id, action, search, from_time, to_time)

    rows = db.execute(
        f"SELECT q.id, q.client_ip, p.name as profile_name, q.domain, q.query_type, "
        f"q.action, q.response_ms, q.logged_at "
        f"FROM query_log q LEFT JOIN profiles p ON q.profile_id = p.id "
        f"{where} ORDER BY q.logged_at DESC",
        params,
    ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "client_ip", "profile_name", "domain", "query_type", "action", "response_ms", "logged_at"])
    for row in rows:
        writer.writerow([row["id"], row["client_ip"], row["profile_name"], row["domain"],
                         row["query_type"], row["action"], row["response_ms"], row["logged_at"]])

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=queries.csv"},
    )
