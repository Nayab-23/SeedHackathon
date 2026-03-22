"""Profiles and devices CRUD routes."""

import uuid
from fastapi import APIRouter, HTTPException

from dashboard.database import get_db
from dashboard.models import CreateProfileRequest, UpdateProfileRequest, AddDeviceRequest

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def _get_profile_response(db, profile_row) -> dict:
    """Build a full profile response with devices, active focus, and stats."""
    profile_id = profile_row["id"]

    # Devices
    devices = db.execute(
        "SELECT id, ip, label FROM devices WHERE profile_id = ?", (profile_id,)
    ).fetchall()

    # Active focus note
    focus_row = db.execute(
        "SELECT id, note, strictness, starts_at, expires_at FROM focus_notes "
        "WHERE profile_id = ? AND ended_early = 0 AND expires_at > datetime('now') "
        "AND starts_at <= datetime('now') "
        "ORDER BY expires_at DESC LIMIT 1",
        (profile_id,),
    ).fetchone()

    active_focus = None
    if focus_row:
        # Calculate remaining minutes
        remaining = db.execute(
            "SELECT CAST((julianday(?) - julianday('now')) * 1440 AS INTEGER)",
            (focus_row["expires_at"],),
        ).fetchone()[0]
        active_focus = {
            "id": focus_row["id"],
            "note": focus_row["note"],
            "strictness": focus_row["strictness"],
            "starts_at": focus_row["starts_at"],
            "expires_at": focus_row["expires_at"],
            "remaining_minutes": max(0, remaining or 0),
        }

    # Today's stats
    stats_row = db.execute(
        "SELECT COUNT(*) as total, "
        "SUM(CASE WHEN action = 'BLOCKED' THEN 1 ELSE 0 END) as blocked "
        "FROM query_log WHERE profile_id = ? AND logged_at >= date('now')",
        (profile_id,),
    ).fetchone()

    return {
        "id": profile_row["id"],
        "name": profile_row["name"],
        "created_at": profile_row["created_at"],
        "devices": [dict(d) for d in devices],
        "active_focus": active_focus,
        "stats": {
            "queries_today": stats_row["total"] or 0,
            "blocked_today": stats_row["blocked"] or 0,
        },
    }


@router.get("")
def get_profiles():
    db = get_db()
    rows = db.execute("SELECT id, name, created_at FROM profiles ORDER BY name").fetchall()
    profiles = [_get_profile_response(db, row) for row in rows]
    return {"profiles": profiles}


@router.post("", status_code=201)
def create_profile(body: CreateProfileRequest):
    db = get_db()
    profile_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO profiles (id, name) VALUES (?, ?)",
        (profile_id, body.name),
    )
    db.commit()

    row = db.execute("SELECT id, name, created_at FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    return _get_profile_response(db, row)


@router.put("/{profile_id}")
def update_profile(
    profile_id: str,
    body: UpdateProfileRequest,
    
):
    db = get_db()
    result = db.execute(
        "UPDATE profiles SET name = ? WHERE id = ?",
        (body.name, profile_id),
    )
    db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="profile not found")

    row = db.execute("SELECT id, name, created_at FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    return _get_profile_response(db, row)


@router.delete("/{profile_id}")
def delete_profile(profile_id: str):
    db = get_db()
    result = db.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
    db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="profile not found")

    return {"ok": True}


@router.post("/{profile_id}/devices", status_code=201)
def add_device(
    profile_id: str,
    body: AddDeviceRequest,
    
):
    db = get_db()

    # Verify profile exists
    profile = db.execute("SELECT id FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    if not profile:
        raise HTTPException(status_code=404, detail="profile not found")

    try:
        cursor = db.execute(
            "INSERT INTO devices (profile_id, ip, label) VALUES (?, ?, ?)",
            (profile_id, body.ip, body.label),
        )
        db.commit()
    except Exception:
        raise HTTPException(status_code=409, detail="IP already assigned to a device")

    device = db.execute(
        "SELECT id, profile_id, ip, label, added_at FROM devices WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return dict(device)


@router.delete("/{profile_id}/devices/{device_id}")
def delete_device(
    profile_id: str,
    device_id: int,
    
):
    db = get_db()
    result = db.execute(
        "DELETE FROM devices WHERE id = ? AND profile_id = ?",
        (device_id, profile_id),
    )
    db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="device not found")

    return {"ok": True}
