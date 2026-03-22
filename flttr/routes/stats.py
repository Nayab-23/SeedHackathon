from fastapi import APIRouter
from flttr.database import get_connection

router = APIRouter(prefix="/api/stats", tags=["stats"])

db_path: str = ""


@router.get("/overview")
def overview():
    conn = get_connection(db_path)
    row = conn.execute("""
        SELECT
            COUNT(*) as total_queries,
            SUM(CASE WHEN action = 'BLOCKED' THEN 1 ELSE 0 END) as blocked,
            SUM(CASE WHEN action = 'ALLOWED' THEN 1 ELSE 0 END) as allowed
        FROM query_log
        WHERE date(logged_at) = date('now')
    """).fetchone()
    conn.close()

    total = row["total_queries"] or 0
    blocked = row["blocked"] or 0
    allowed = row["allowed"] or 0
    block_rate = round((blocked / total * 100), 1) if total > 0 else 0

    return {
        "today": {
            "total_queries": total,
            "blocked": blocked,
            "allowed": allowed,
            "block_rate": block_rate,
        }
    }


@router.get("/hourly")
def hourly(date: str = ""):
    conn = get_connection(db_path)
    if date:
        where = "WHERE date(logged_at) = ?"
        params = [date]
    else:
        where = "WHERE date(logged_at) = date('now')"
        params = []

    rows = conn.execute(f"""
        SELECT
            CAST(strftime('%H', logged_at) AS INTEGER) as hour,
            COUNT(*) as total,
            SUM(CASE WHEN action = 'BLOCKED' THEN 1 ELSE 0 END) as blocked
        FROM query_log
        {where}
        GROUP BY hour
        ORDER BY hour
    """, params).fetchall()
    conn.close()

    hour_map = {r["hour"]: {"hour": r["hour"], "total": r["total"], "blocked": r["blocked"]} for r in rows}
    hours = [hour_map.get(h, {"hour": h, "total": 0, "blocked": 0}) for h in range(24)]

    return {"hours": hours}


@router.get("/top_blocked")
def top_blocked(limit: int = 10):
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT domain, COUNT(*) as count
        FROM query_log
        WHERE action = 'BLOCKED'
        GROUP BY domain
        ORDER BY count DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()

    return {"domains": [dict(r) for r in rows]}


@router.get("/focus_agent")
def focus_agent_stats():
    """Show domains auto-blocked by the focus agent."""
    conn = get_connection(db_path)
    rows = conn.execute("""
        SELECT domain, reason, added_at
        FROM domain_lists
        WHERE added_by = 'focus-agent'
        ORDER BY added_at DESC
        LIMIT 100
    """).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) FROM domain_lists WHERE added_by = 'focus-agent'"
    ).fetchone()[0]
    conn.close()

    return {
        "focus_agent_blocks": [dict(r) for r in rows],
        "total": total,
    }
