"""Focus notes routes: create, extend, end early, history."""

import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from dashboard.database import get_db
from dashboard.models import CreateFocusRequest, ExtendFocusRequest

router = APIRouter(prefix="/api/focus", tags=["focus"])


def _format_note(row, db) -> dict:
    """Format a focus note row into a response dict."""
    now = datetime.utcnow()
    try:
        expires = datetime.fromisoformat(row["expires_at"])
        starts = datetime.fromisoformat(row["starts_at"])
        remaining = max(0, int((expires - now).total_seconds() / 60))
        active = not row["ended_early"] and expires > now and starts <= now
    except Exception:
        remaining = 0
        active = False

    # Get profile name
    profile_name = None
    if row["profile_id"]:
        p = db.execute("SELECT name FROM profiles WHERE id = ?", (row["profile_id"],)).fetchone()
        if p:
            profile_name = p["name"]

    return {
        "id": row["id"],
        "profile_id": row["profile_id"],
        "profile_name": profile_name,
        "note": row["note"],
        "strictness": row["strictness"],
        "starts_at": row["starts_at"],
        "expires_at": row["expires_at"],
        "remaining_minutes": remaining,
        "active": active,
    }


@router.get("")
def get_focus_notes(
    profile_id: Optional[str] = None,
    active_only: Optional[bool] = False,
    
):
    db = get_db()
    where_clauses = []
    params = []

    if profile_id:
        where_clauses.append("profile_id = ?")
        params.append(profile_id)

    if active_only:
        where_clauses.append("ended_early = 0")
        where_clauses.append("expires_at > datetime('now')")
        where_clauses.append("starts_at <= datetime('now')")

    where = ""
    if where_clauses:
        where = "WHERE " + " AND ".join(where_clauses)

    rows = db.execute(
        f"SELECT * FROM focus_notes {where} ORDER BY created_at DESC", params
    ).fetchall()

    return {"notes": [_format_note(r, db) for r in rows]}


@router.post("", status_code=201)
def create_focus_note(body: CreateFocusRequest):
    db = get_db()

    # Verify profile exists
    profile = db.execute("SELECT id FROM profiles WHERE id = ?", (body.profile_id,)).fetchone()
    if not profile:
        raise HTTPException(status_code=404, detail="profile not found")

    if body.strictness not in ("relaxed", "moderate", "strict"):
        raise HTTPException(status_code=400, detail="strictness must be relaxed, moderate, or strict")

    note_id = str(uuid.uuid4())
    now = datetime.utcnow()
    starts_at = now.isoformat()
    expires_at = (now + timedelta(minutes=body.duration_minutes)).isoformat()

    db.execute(
        "INSERT INTO focus_notes (id, profile_id, note, strictness, starts_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (note_id, body.profile_id, body.note, body.strictness, starts_at, expires_at),
    )
    db.commit()

    row = db.execute("SELECT * FROM focus_notes WHERE id = ?", (note_id,)).fetchone()
    return _format_note(row, db)


@router.put("/{note_id}/extend")
def extend_focus(
    note_id: str,
    body: ExtendFocusRequest,
    
):
    db = get_db()
    row = db.execute("SELECT * FROM focus_notes WHERE id = ?", (note_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="focus note not found")

    try:
        current_expires = datetime.fromisoformat(row["expires_at"])
    except Exception:
        raise HTTPException(status_code=500, detail="invalid expires_at format")

    new_expires = (current_expires + timedelta(minutes=body.extra_minutes)).isoformat()

    db.execute(
        "UPDATE focus_notes SET expires_at = ? WHERE id = ?",
        (new_expires, note_id),
    )
    db.commit()

    row = db.execute("SELECT * FROM focus_notes WHERE id = ?", (note_id,)).fetchone()
    return _format_note(row, db)


@router.delete("/{note_id}")
def end_focus_early(note_id: str):
    db = get_db()
    result = db.execute(
        "UPDATE focus_notes SET ended_early = 1 WHERE id = ?",
        (note_id,),
    )
    db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="focus note not found")

    return {"ok": True}


@router.get("/history")
def get_focus_history(
    profile_id: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    
):
    db = get_db()
    where_clauses = [f"created_at >= datetime('now', '-{days} days')"]
    params = []

    if profile_id:
        where_clauses.append("profile_id = ?")
        params.append(profile_id)

    where = "WHERE " + " AND ".join(where_clauses)

    rows = db.execute(
        f"SELECT * FROM focus_notes {where} ORDER BY created_at DESC", params
    ).fetchall()

    return {"notes": [_format_note(r, db) for r in rows]}
