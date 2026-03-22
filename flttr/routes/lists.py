import math
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from flttr.database import get_connection

router = APIRouter(prefix="/api/lists", tags=["lists"])

# These get set by app.py at startup
db_path: str = ""
domain_filter = None
blacklist_txt_path: str = ""


class AddDomainRequest(BaseModel):
    domain: str
    reason: Optional[str] = None
    added_by: str = "manual"


class BulkAddRequest(BaseModel):
    domains: list[str]
    reason: Optional[str] = None


def _regenerate_blacklist_txt():
    conn = get_connection(db_path)
    rows = conn.execute("SELECT domain FROM domain_lists ORDER BY domain").fetchall()
    conn.close()
    with open(blacklist_txt_path, "w") as f:
        f.write("# FLTTR blacklist — auto-generated from database\n")
        for row in rows:
            f.write(row["domain"] + "\n")
    if domain_filter:
        domain_filter.reload()


@router.get("")
def get_blacklist(search: str = "", page: int = 1, per_page: int = 50):
    conn = get_connection(db_path)
    if search:
        where = "WHERE domain LIKE ?"
        params = [f"%{search}%"]
    else:
        where = ""
        params = []

    total = conn.execute(f"SELECT COUNT(*) FROM domain_lists {where}", params).fetchone()[0]
    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT id, domain, added_by, reason, added_at FROM domain_lists {where} ORDER BY added_at DESC LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()
    conn.close()

    return {
        "domains": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "pages": math.ceil(total / per_page) if total > 0 else 1,
    }


@router.post("", status_code=201)
def add_domain(req: AddDomainRequest):
    domain = req.domain.strip().lower().rstrip(".")
    if not domain:
        raise HTTPException(status_code=400, detail="Domain cannot be empty")

    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO domain_lists (domain, added_by, reason) VALUES (?, ?, ?)",
            (domain, req.added_by, req.reason),
        )
        conn.commit()
        new_id = cursor.lastrowid
    except Exception:
        conn.close()
        raise HTTPException(status_code=409, detail="Domain already exists")
    conn.close()

    _regenerate_blacklist_txt()
    return {"ok": True, "id": new_id}


@router.post("/bulk", status_code=201)
def bulk_add(req: BulkAddRequest):
    added = 0
    duplicates = 0
    conn = get_connection(db_path)
    for d in req.domains:
        domain = d.strip().lower().rstrip(".")
        if not domain:
            continue
        try:
            conn.execute(
                "INSERT INTO domain_lists (domain, added_by, reason) VALUES (?, 'manual', ?)",
                (domain, req.reason),
            )
            added += 1
        except Exception:
            duplicates += 1
    conn.commit()
    conn.close()

    _regenerate_blacklist_txt()
    return {"ok": True, "added": added, "duplicates": duplicates}


@router.delete("/{domain}")
def delete_domain(domain: str):
    domain = domain.strip().lower().rstrip(".")
    conn = get_connection(db_path)
    result = conn.execute("DELETE FROM domain_lists WHERE domain = ?", (domain,))
    conn.commit()
    conn.close()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Domain not found")

    _regenerate_blacklist_txt()
    return {"ok": True}
