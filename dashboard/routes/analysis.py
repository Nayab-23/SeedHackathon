"""Analysis log routes: read/write for LangChain agent."""

from fastapi import APIRouter, Query
from typing import Optional

from dashboard.database import get_db
from dashboard.models import CreateAnalysisRequest

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("")
def get_analyses(
    risk_level: Optional[str] = None,
    profile_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    
):
    db = get_db()
    where_clauses = []
    params = []

    if risk_level:
        where_clauses.append("a.risk_level = ?")
        params.append(risk_level)

    if profile_id:
        where_clauses.append("a.profile_id = ?")
        params.append(profile_id)

    where = ""
    if where_clauses:
        where = "WHERE " + " AND ".join(where_clauses)

    total = db.execute(
        f"SELECT COUNT(*) FROM analysis_log a {where}", params
    ).fetchone()[0]

    offset = (page - 1) * per_page
    rows = db.execute(
        f"SELECT a.id, a.domain, a.profile_id, p.name as profile_name, "
        f"a.risk_level, a.category, a.reasoning, a.action_taken, a.analyzed_at "
        f"FROM analysis_log a LEFT JOIN profiles p ON a.profile_id = p.id "
        f"{where} ORDER BY a.analyzed_at DESC LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()

    return {
        "analyses": [dict(r) for r in rows],
        "total": total,
    }


@router.post("", status_code=201)
def create_analysis(body: CreateAnalysisRequest):
    db = get_db()
    cursor = db.execute(
        "INSERT INTO analysis_log (domain, profile_id, risk_level, category, reasoning, action_taken) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (body.domain, body.profile_id, body.risk_level, body.category, body.reasoning, body.action_taken),
    )
    db.commit()
    return {"id": cursor.lastrowid}
