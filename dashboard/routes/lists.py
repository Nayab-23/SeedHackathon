"""Blacklist/Whitelist CRUD routes with .txt regeneration and filter reload."""

import os
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from typing import Optional

from dashboard.database import get_db
from dashboard.models import AddDomainRequest, BulkImportRequest

router = APIRouter(prefix="/api/lists", tags=["lists"])

# These will be set by the app factory
_lists_dir: str = ""
_domain_filter = None


def configure(lists_dir: str, domain_filter=None):
    """Configure paths and filter reference."""
    global _lists_dir, _domain_filter
    _lists_dir = lists_dir
    _domain_filter = domain_filter


def _regenerate_txt(list_type: str):
    """Regenerate .txt file from database and reload the filter."""
    db = get_db()
    rows = db.execute(
        "SELECT domain FROM domain_lists WHERE list_type = ? ORDER BY domain",
        (list_type,),
    ).fetchall()

    filepath = os.path.join(_lists_dir, f"{list_type}.txt")
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w") as f:
        for row in rows:
            f.write(row["domain"] + "\n")

    if _domain_filter is not None:
        try:
            _domain_filter.reload()
        except Exception as e:
            print(f"[Lists] Filter reload error: {e}")


def _validate_list_type(list_type: str):
    if list_type not in ("blacklist", "whitelist"):
        raise HTTPException(status_code=400, detail="list_type must be 'blacklist' or 'whitelist'")


@router.get("/{list_type}")
def get_list(
    list_type: str,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    sort: str = "added_at",
    order: str = "desc",
    
):
    _validate_list_type(list_type)
    db = get_db()

    # Validate sort column
    allowed_sorts = {"added_at", "domain", "added_by", "reason"}
    if sort not in allowed_sorts:
        sort = "added_at"
    if order not in ("asc", "desc"):
        order = "desc"

    where = "WHERE list_type = ?"
    params = [list_type]
    if search:
        where += " AND domain LIKE ?"
        params.append(f"%{search}%")

    # Get total count
    total = db.execute(f"SELECT COUNT(*) FROM domain_lists {where}", params).fetchone()[0]

    # Get paginated results
    offset = (page - 1) * per_page
    rows = db.execute(
        f"SELECT id, domain, added_by, reason, added_at FROM domain_lists {where} "
        f"ORDER BY {sort} {order} LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()

    pages = max(1, (total + per_page - 1) // per_page)

    return {
        "domains": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.post("/{list_type}", status_code=201)
def add_domain(
    list_type: str,
    body: AddDomainRequest,
    
):
    _validate_list_type(list_type)
    db = get_db()
    domain = body.domain.strip().lower()
    if not domain:
        raise HTTPException(status_code=400, detail="domain is required")

    try:
        cursor = db.execute(
            "INSERT INTO domain_lists (domain, list_type, added_by, reason) VALUES (?, ?, 'manual', ?)",
            (domain, list_type, body.reason),
        )
        db.commit()
    except Exception:
        raise HTTPException(status_code=409, detail="domain already exists in this list")

    _regenerate_txt(list_type)
    return {"ok": True, "id": cursor.lastrowid}


@router.post("/{list_type}/bulk", status_code=201)
def bulk_import(
    list_type: str,
    body: BulkImportRequest,
    
):
    _validate_list_type(list_type)
    db = get_db()
    added = 0
    duplicates = 0

    for raw_domain in body.domains:
        domain = raw_domain.strip().lower()
        if not domain or domain.startswith("#"):
            continue
        try:
            db.execute(
                "INSERT INTO domain_lists (domain, list_type, added_by, reason) VALUES (?, ?, 'manual', ?)",
                (domain, list_type, body.reason),
            )
            added += 1
        except Exception:
            duplicates += 1

    db.commit()
    _regenerate_txt(list_type)
    return {"ok": True, "added": added, "duplicates": duplicates}


@router.delete("/{list_type}/{domain}")
def delete_domain(
    list_type: str,
    domain: str,
    
):
    _validate_list_type(list_type)
    db = get_db()
    domain = domain.strip().lower()

    result = db.execute(
        "DELETE FROM domain_lists WHERE domain = ? AND list_type = ?",
        (domain, list_type),
    )
    db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="domain not found in list")

    _regenerate_txt(list_type)
    return {"ok": True}


@router.post("/{list_type}/import", status_code=201)
async def import_file(
    list_type: str,
    file: UploadFile = File(...),
    
):
    _validate_list_type(list_type)
    db = get_db()

    content = await file.read()
    lines = content.decode("utf-8", errors="ignore").splitlines()

    added = 0
    duplicates = 0

    for line in lines:
        domain = line.strip().lower()
        if not domain or domain.startswith("#"):
            continue
        try:
            db.execute(
                "INSERT INTO domain_lists (domain, list_type, added_by, reason) VALUES (?, ?, 'manual', 'file import')",
                (domain, list_type),
            )
            added += 1
        except Exception:
            duplicates += 1

    db.commit()
    _regenerate_txt(list_type)
    return {"ok": True, "added": added, "duplicates": duplicates}
