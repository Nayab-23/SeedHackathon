import asyncio
import logging
import os
import re
import time
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session as DBSession

from backend.argue import (
    add_domain_to_dns_blocklist,
    evaluate_argument,
    normalize_domain,
    remove_domain_from_dns_blocklist,
    sync_dns_state,
    update_dns_allowlist,
)
from backend.database import (
    Allowlist,
    Blocklist,
    Event,
    Session,
    SessionLocal,
    engine,
    get_db,
    init_db,
)
from backend.reachy_control import (
    async_nod_yes,
    async_react_to_state,
    async_shake_no,
    controller as reachy,
)
from backend.vision import (
    CAPTURE_INTERVAL,
    frame_buffer,
    state_manager,
    stop_vision_loop,
    vision_loop,
)
from backend.voice_loop import (
    get_conversation_transcript,
    get_voice_status,
    set_listening_enabled,
    set_debug_callback,
    start_voice_loop,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DNS_LOG_PATH = Path(os.getenv("DNS_LOG_PATH", str(BASE_DIR / "dnsmasq.log")))
DNS_LOG_LINE_SCAN = int(os.getenv("DNS_LOG_LINE_SCAN", "4000"))
DNS_LOG_RE = re.compile(
    r"^(?P<timestamp>[A-Z][a-z]{2}\s+\d+\s+\d{2}:\d{2}:\d{2})\s+(?:\S+\s+)?dnsmasq(?:\[\d+\])?:\s+(?P<body>.*)$"
)

_vision_task: asyncio.Task | None = None
_start_time: float = 0
_voice_debug_events = deque(maxlen=100)


# ---------------------------------------------------------------------------
# State-change hook
# ---------------------------------------------------------------------------

def _on_state_change(new_state: str, _prev: str):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(async_react_to_state(new_state))
    except RuntimeError:
        pass


# ---------------------------------------------------------------------------
# Startup diagnostics
# ---------------------------------------------------------------------------

def _check_db() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _print_banner():
    ok = "\033[32m✓\033[0m"
    fail = "\033[31m✗\033[0m"
    warn = "\033[33m⚠\033[0m"

    db_ok = _check_db()
    cam_ok = frame_buffer.get_jpeg() is not None
    reachy_ok = reachy.connected

    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info("  StudyGuard — Startup Diagnostics")
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info("  Database:  %s %s", ok if db_ok else fail, "connected" if db_ok else "FAILED")
    log.info("  Camera:    %s %s", ok if cam_ok else warn, "streaming" if cam_ok else "waiting for first frame (will retry)")
    log.info("  Reachy:    %s %s", ok if reachy_ok else warn, "connected" if reachy_ok else "not connected (gestures disabled)")
    log.info("  Frontend:  %s %s", ok if (FRONTEND_DIR / "index.html").exists() else fail, str(FRONTEND_DIR))
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


def _record_event(event_type: str, detail: str | None = None) -> None:
    db = SessionLocal()
    try:
        db.add(Event(event_type=event_type, detail=detail))
        db.commit()
    except Exception:
        log.exception("Failed to record event: %s", event_type)
        db.rollback()
    finally:
        db.close()


def _push_voice_debug(kind: str, text: str) -> None:
    _voice_debug_events.appendleft(
        {
            "kind": kind,
            "text": text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


def _tail_lines(path: Path, limit: int) -> list[str]:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return handle.readlines()[-limit:]
    except FileNotFoundError:
        return []
    except Exception:
        log.exception("Failed reading DNS log file: %s", path)
        return []


def _parse_dns_log_rows(limit: int) -> list[dict]:
    rows = _tail_lines(DNS_LOG_PATH, DNS_LOG_LINE_SCAN)
    grouped: dict[str, dict] = {}
    order: list[str] = []

    for raw_line in rows:
        match = DNS_LOG_RE.match(raw_line.strip())
        if not match:
            continue

        timestamp_text = match.group("timestamp")
        body = match.group("body").strip()
        serial = None
        source_client = ""

        extra = re.match(r"^(?P<serial>\d+)\s+(?P<src>[0-9a-fA-F:.]+)/\d+\s+(?P<rest>.*)$", body)
        if extra:
            serial = extra.group("serial")
            source_client = extra.group("src")
            body = extra.group("rest").strip()

        key = serial or f"line-{len(order)}"
        entry = grouped.get(key)
        if entry is None:
            entry = {
                "id": key,
                "timestamp_text": timestamp_text,
                "kind": "dns",
                "domain": "",
                "client": source_client,
                "outcome": "",
                "blocked": False,
                "raw": [],
            }
            grouped[key] = entry
            order.append(key)

        entry["timestamp_text"] = timestamp_text
        if source_client and not entry["client"]:
            entry["client"] = source_client
        entry["raw"].append(body)

        query = re.search(r"query\[[^\]]+\]\s+([^\s]+)\s+from\s+([^\s]+)", body)
        forwarded = re.search(r"forwarded\s+([^\s]+)\s+to\s+([^\s]+)", body)
        config = re.search(r"config\s+([^\s]+)\s+is\s+(.+)$", body)
        reply = re.search(r"reply\s+([^\s]+)\s+is\s+(.+)$", body)
        cached = re.search(r"cached\s+([^\s]+)\s+is\s+(.+)$", body)

        if query:
            entry["kind"] = "query"
            entry["domain"] = query.group(1)
            entry["client"] = query.group(2)
        elif forwarded:
            entry["kind"] = "forwarded"
            entry["domain"] = forwarded.group(1)
            entry["outcome"] = f"forwarded to {forwarded.group(2)}"
        elif config:
            entry["kind"] = "config"
            entry["domain"] = config.group(1)
            entry["outcome"] = f"config {config.group(2)}"
            if config.group(2).strip() in {"0.0.0.0", "::"}:
                entry["blocked"] = True
        elif reply:
            entry["kind"] = "reply"
            entry["domain"] = reply.group(1)
            entry["outcome"] = f"reply {reply.group(2)}"
            if reply.group(2).strip() in {"0.0.0.0", "::"}:
                entry["blocked"] = True
        elif cached:
            entry["kind"] = "cached"
            entry["domain"] = cached.group(1)
            entry["outcome"] = f"cached {cached.group(2)}"
            if cached.group(2).strip() in {"0.0.0.0", "::"}:
                entry["blocked"] = True

    parsed = []
    for key in reversed(order):
        entry = grouped[key]
        if not entry["domain"]:
            continue
        parsed.append(
            {
                "id": entry["id"],
                "timestamp_text": entry["timestamp_text"],
                "kind": entry["kind"],
                "domain": entry["domain"],
                "client": entry["client"],
                "outcome": entry["outcome"],
                "blocked": entry["blocked"],
                "raw": " | ".join(entry["raw"]),
            }
        )
        if len(parsed) >= limit:
            break
    return parsed


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _vision_task, _start_time
    _start_time = time.time()

    log.info("Starting StudyGuard …")

    init_db()
    log.info("Database initialised — tables created, blocklist seeded")

    if sync_dns_state():
        log.info("DNS block/allow state synchronized to dnsmasq")
    else:
        log.warning("DNS block/allow state failed to synchronize")

    if reachy.reconnect():
        log.info("Reachy connection verified at startup")
    else:
        log.warning("Reachy connection not available at startup")

    state_manager.on_state_change(_on_state_change)

    _vision_task = asyncio.create_task(vision_loop())
    log.info("Vision monitoring loop launched (classifies every %.1fs)", CAPTURE_INTERVAL)

    set_debug_callback(_push_voice_debug)
    start_voice_loop(
        state_manager=state_manager,
        reachy=reachy,
    )
    log.info("Local voice loop launched")

    await asyncio.sleep(2)

    _print_banner()
    log.info("StudyGuard is ready — accepting connections")

    yield

    log.info("Shutting down …")
    stop_vision_loop()
    if _vision_task is not None:
        _vision_task.cancel()
        try:
            await _vision_task
        except asyncio.CancelledError:
            pass
    reachy.disconnect()
    log.info("Shutdown complete")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="StudyGuard", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ArgueRequest(BaseModel):
    domain: str
    argument: str


class BlocklistAdd(BaseModel):
    domain: str


class VoiceActionRequest(BaseModel):
    action: str
    domain: str
    minutes: int = 30


class VoiceDebugEvent(BaseModel):
    kind: str
    text: str


class VoiceListenRequest(BaseModel):
    enabled: bool = True
    duration_seconds: int = 20


# ---------------------------------------------------------------------------
# Routes — pages
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def index():
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(404, "frontend/index.html not found")
    return FileResponse(str(index_path), media_type="text/html")


# ---------------------------------------------------------------------------
# Routes — health
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    if not reachy.connected:
        await asyncio.get_running_loop().run_in_executor(None, reachy.reconnect)
    db_ok = False
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception:
        pass

    cam_ok = frame_buffer.get_jpeg() is not None
    reachy_ok = reachy.connected
    all_ok = db_ok

    return {
        "status": "ok" if all_ok else "degraded",
        "uptime_seconds": round(time.time() - _start_time, 1),
        "camera": cam_ok,
        "camera_frame_age_seconds": round(max(0.0, time.time() - frame_buffer.get_timestamp()), 3) if cam_ok else None,
        "reachy": reachy_ok,
        "db": db_ok,
    }


# ---------------------------------------------------------------------------
# Routes — status & stats
# ---------------------------------------------------------------------------

@app.get("/api/status")
async def get_status():
    if not reachy.connected:
        await asyncio.get_running_loop().run_in_executor(None, reachy.reconnect)
    state = state_manager.get_current_state()
    voice = get_voice_status()
    return {
        "state": state,
        "study_seconds_today": round(state_manager.get_study_seconds_today(), 1),
        "distracted_seconds_today": round(state_manager.get_distracted_seconds_today(), 1),
        "is_studying": state == "studying",
        "reachy_connected": reachy.connected,
        "voice_state": voice["state"],
        "voice_running": voice["running"],
        "agora_agent_running": voice["running"],
    }


@app.get("/api/stats/today")
async def stats_today(db: DBSession = Depends(get_db)):
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )

    events_count = (
        db.query(func.count(Event.id))
        .filter(Event.timestamp >= today_start)
        .scalar()
    )

    sessions = (
        db.query(Session)
        .filter(Session.start_time >= today_start)
        .order_by(Session.start_time.desc())
        .all()
    )

    return {
        "total_study_seconds": round(state_manager.get_study_seconds_today(), 1),
        "total_distracted_seconds": round(state_manager.get_distracted_seconds_today(), 1),
        "events_count": events_count,
        "sessions": [
            {
                "id": s.id,
                "start_time": s.start_time.isoformat() if s.start_time else None,
                "end_time": s.end_time.isoformat() if s.end_time else None,
                "total_study_seconds": s.total_study_seconds,
                "total_distracted_seconds": s.total_distracted_seconds,
            }
            for s in sessions
        ],
    }


# ---------------------------------------------------------------------------
# Routes — events
# ---------------------------------------------------------------------------

@app.get("/api/events")
async def get_events(
    limit: int = Query(50, ge=1, le=500),
    db: DBSession = Depends(get_db),
):
    rows = (
        db.query(Event)
        .order_by(Event.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": e.id,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "event_type": e.event_type,
            "detail": e.detail,
            "session_id": e.session_id,
        }
        for e in rows
    ]


@app.get("/api/logs/dns")
async def dns_logs(limit: int = Query(100, ge=1, le=500)):
    return _parse_dns_log_rows(limit)


# ---------------------------------------------------------------------------
# Routes — allowlist
# ---------------------------------------------------------------------------

@app.get("/api/allowlist")
async def get_allowlist(db: DBSession = Depends(get_db)):
    rows = db.query(Allowlist).order_by(Allowlist.granted_at.desc()).all()
    return [
        {
            "id": a.id,
            "domain": a.domain,
            "granted_at": a.granted_at.isoformat() if a.granted_at else None,
            "expires_at": a.expires_at.isoformat() if a.expires_at else None,
            "reason": a.reason,
        }
        for a in rows
    ]


# ---------------------------------------------------------------------------
# Routes — blocklist
# ---------------------------------------------------------------------------

@app.get("/api/blocklist")
async def get_blocklist(db: DBSession = Depends(get_db)):
    rows = db.query(Blocklist).order_by(Blocklist.added_at.desc()).all()
    return [
        {
            "id": b.id,
            "domain": b.domain,
            "added_at": b.added_at.isoformat() if b.added_at else None,
        }
        for b in rows
    ]


@app.post("/api/blocklist", status_code=201)
async def add_to_blocklist(body: BlocklistAdd, db: DBSession = Depends(get_db)):
    domain = normalize_domain(body.domain)
    if not domain:
        raise HTTPException(400, "valid domain or URL is required")
    exists = db.query(Blocklist).filter_by(domain=domain).first()
    if exists:
        raise HTTPException(409, f"{domain} is already blocked")
    entry = Blocklist(domain=domain)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    add_domain_to_dns_blocklist(domain)
    return {"id": entry.id, "domain": entry.domain, "added_at": entry.added_at.isoformat()}


@app.delete("/api/blocklist/{domain}")
async def remove_from_blocklist(domain: str, db: DBSession = Depends(get_db)):
    normalized = normalize_domain(domain)
    if not normalized:
        raise HTTPException(400, "valid domain or URL is required")
    entry = db.query(Blocklist).filter_by(domain=normalized).first()
    if not entry:
        raise HTTPException(404, f"{domain} not found in blocklist")
    db.delete(entry)
    db.commit()
    remove_domain_from_dns_blocklist(normalized)
    return {"removed": normalized}


# ---------------------------------------------------------------------------
# Routes — camera
# ---------------------------------------------------------------------------

@app.get("/api/camera")
async def get_camera_frame():
    jpeg = frame_buffer.get_jpeg()
    if jpeg is None:
        raise HTTPException(503, "No camera frame available yet")
    return Response(content=jpeg, media_type="image/jpeg")


@app.get("/api/camera/stream")
async def get_camera_stream():
    async def mjpeg_stream():
        last_timestamp = 0.0
        while True:
            jpeg = frame_buffer.get_jpeg()
            timestamp = frame_buffer.get_timestamp()
            if jpeg is None or timestamp <= last_timestamp:
                await asyncio.sleep(0.005)
                continue
            last_timestamp = timestamp
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Cache-Control: no-cache\r\n\r\n"
                + jpeg
                + b"\r\n"
            )

    return StreamingResponse(
        mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        },
    )


# ---------------------------------------------------------------------------
# Routes — argue
# ---------------------------------------------------------------------------

@app.post("/api/argue")
async def argue(body: ArgueRequest):
    domain = normalize_domain(body.domain)
    argument = body.argument.strip()
    if not domain or not argument:
        raise HTTPException(400, "domain and argument are required")

    study_stats = {
        "study_seconds": state_manager.get_study_seconds_today(),
        "distracted_seconds": state_manager.get_distracted_seconds_today(),
    }

    decision = await evaluate_argument(domain, argument, study_stats)

    if decision["decision"] == "grant":
        await update_dns_allowlist(domain, decision["duration_minutes"])
        await async_nod_yes()
    else:
        await async_shake_no()

    return decision


@app.get("/api/voice/status")
async def voice_status():
    if not reachy.connected:
        await asyncio.get_running_loop().run_in_executor(None, reachy.reconnect)
    voice = get_voice_status()
    return {
        "agent_running": voice["running"],
        "running": voice["running"],
        "state": voice["state"],
        "is_speaking": voice["is_speaking"],
        "last_heard": voice["last_heard"],
        "last_error": voice["last_error"],
        "listening_enabled": voice["listening_enabled"],
        "armed_until": voice["armed_until"],
    }


@app.post("/api/voice/listening")
async def voice_listening(body: VoiceListenRequest):
    voice = set_listening_enabled(bool(body.enabled), max(1, min(120, int(body.duration_seconds or 20))))
    return {
        "running": voice["running"],
        "state": voice["state"],
        "is_speaking": voice["is_speaking"],
        "last_heard": voice["last_heard"],
        "last_error": voice["last_error"],
        "listening_enabled": voice["listening_enabled"],
        "armed_until": voice["armed_until"],
    }


@app.get("/api/voice/debug")
async def voice_debug():
    return list(_voice_debug_events)


@app.get("/api/voice/conversation")
async def voice_conversation():
    return get_conversation_transcript()


@app.post("/api/voice/debug")
async def post_voice_debug(body: VoiceDebugEvent):
    _push_voice_debug((body.kind or "info")[:40], (body.text or "")[:2000])
    return {"status": "ok"}


@app.post("/api/voice/action")
async def voice_action(body: VoiceActionRequest):
    action = (body.action or "").strip().lower()
    domain = normalize_domain(body.domain)
    if action not in {"grant", "deny", "alert"}:
        raise HTTPException(400, "action must be grant, deny, or alert")
    if action != "alert" and not domain:
        raise HTTPException(400, "valid domain or URL is required")

    if action == "grant":
        minutes = max(1, min(60, int(body.minutes or 30)))
        await update_dns_allowlist(domain, minutes)
        await async_nod_yes()
        detail = f"domain={domain}|mins={minutes}|reason=Manual voice override"
        _record_event("site_granted", detail)
        print(f"[VOICE ACTION] GRANT {domain} for {minutes} minutes", flush=True)
    elif action == "deny":
        await async_shake_no()
        detail = f"domain={domain}|reason=Manual voice override"
        _record_event("site_denied", detail)
        print(f"[VOICE ACTION] DENY {domain}", flush=True)
    else:
        await asyncio.get_running_loop().run_in_executor(None, reachy.alert_distracted)
        _record_event("voice_alert", "Manual voice alert")
        print("[VOICE ACTION] ALERT", flush=True)

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
