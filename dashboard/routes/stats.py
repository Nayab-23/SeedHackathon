"""Stats routes: overview, hourly breakdown, top blocked domains."""

from fastapi import APIRouter, Query
from typing import Optional

from dashboard.database import get_db

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/overview")
def get_overview():
    db = get_db()

    # Today's totals
    today = db.execute(
        "SELECT "
        "COUNT(*) as total, "
        "SUM(CASE WHEN action = 'BLOCKED' THEN 1 ELSE 0 END) as blocked, "
        "SUM(CASE WHEN action = 'ALLOWED' THEN 1 ELSE 0 END) as allowed, "
        "SUM(CASE WHEN action = 'WHITELISTED' THEN 1 ELSE 0 END) as whitelisted "
        "FROM query_log WHERE logged_at >= date('now')"
    ).fetchone()

    total = today["total"] or 0
    blocked = today["blocked"] or 0
    allowed = today["allowed"] or 0
    whitelisted = today["whitelisted"] or 0
    block_rate = round((blocked / total * 100), 1) if total > 0 else 0.0

    # Per-profile stats
    profiles = db.execute("SELECT id, name FROM profiles ORDER BY name").fetchall()
    per_profile = []

    for p in profiles:
        profile_stats = db.execute(
            "SELECT "
            "COUNT(*) as queries, "
            "SUM(CASE WHEN action = 'BLOCKED' THEN 1 ELSE 0 END) as blocked "
            "FROM query_log WHERE profile_id = ? AND logged_at >= date('now')",
            (p["id"],),
        ).fetchone()

        top_domains_rows = db.execute(
            "SELECT domain, COUNT(*) as cnt FROM query_log "
            "WHERE profile_id = ? AND logged_at >= date('now') "
            "GROUP BY domain ORDER BY cnt DESC LIMIT 5",
            (p["id"],),
        ).fetchall()

        top_blocked_rows = db.execute(
            "SELECT domain, COUNT(*) as cnt FROM query_log "
            "WHERE profile_id = ? AND logged_at >= date('now') AND action = 'BLOCKED' "
            "GROUP BY domain ORDER BY cnt DESC LIMIT 5",
            (p["id"],),
        ).fetchall()

        per_profile.append({
            "profile_id": p["id"],
            "name": p["name"],
            "queries": profile_stats["queries"] or 0,
            "blocked": profile_stats["blocked"] or 0,
            "top_domains": [r["domain"] for r in top_domains_rows],
            "top_blocked": [r["domain"] for r in top_blocked_rows],
        })

    return {
        "today": {
            "total_queries": total,
            "blocked": blocked,
            "allowed": allowed,
            "whitelisted": whitelisted,
            "block_rate": block_rate,
        },
        "per_profile": per_profile,
    }


@router.get("/hourly")
def get_hourly(
    date: Optional[str] = None,
    
):
    db = get_db()

    if date:
        date_filter = f"date(logged_at) = '{date}'"
    else:
        date_filter = "logged_at >= date('now')"

    rows = db.execute(
        f"SELECT CAST(strftime('%H', logged_at) AS INTEGER) as hour, "
        f"COUNT(*) as total, "
        f"SUM(CASE WHEN action = 'BLOCKED' THEN 1 ELSE 0 END) as blocked "
        f"FROM query_log WHERE {date_filter} "
        f"GROUP BY hour ORDER BY hour"
    ).fetchall()

    # Fill in all 24 hours
    hour_data = {r["hour"]: {"hour": r["hour"], "total": r["total"], "blocked": r["blocked"] or 0} for r in rows}
    hours = []
    for h in range(24):
        if h in hour_data:
            hours.append(hour_data[h])
        else:
            hours.append({"hour": h, "total": 0, "blocked": 0})

    return {"hours": hours}


@router.get("/top_blocked")
def get_top_blocked(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(20, ge=1, le=100),
    
):
    db = get_db()
    rows = db.execute(
        "SELECT domain, COUNT(*) as count FROM query_log "
        "WHERE action = 'BLOCKED' AND logged_at >= datetime('now', ? || ' days') "
        "GROUP BY domain ORDER BY count DESC LIMIT ?",
        (f"-{days}", limit),
    ).fetchall()

    return {"domains": [{"domain": r["domain"], "count": r["count"]} for r in rows]}
