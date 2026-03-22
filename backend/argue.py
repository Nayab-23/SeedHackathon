import asyncio
import json
import logging
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from dotenv import load_dotenv
from openai import OpenAI

from backend.database import Allowlist, Blocklist, Event, SessionLocal

load_dotenv()

log = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DNS_ALLOWLIST_PATH = os.getenv("DNS_ALLOWLIST_PATH", "/etc/dnsmasq.d/allowlist.conf")
DNS_BLOCKLIST_PATH = os.getenv("DNS_BLOCKLIST_PATH", "/etc/dnsmasq.d/blocklist.conf")

client = OpenAI(api_key=OPENAI_API_KEY)

ARGUE_SYSTEM_PROMPT = """You are an AI parental control assistant. A child is requesting access to a blocked website.
Evaluate their argument fairly but strictly. Consider:
- Is this genuinely educational or necessary?
- How long have they been studying today?
- Is the argument specific and reasonable?

Respond ONLY with valid JSON in this format:
{"decision": "grant" or "deny", "reason": "short explanation", "duration_minutes": 30}

duration_minutes: how long to grant access (15-60 min). Set to 0 if denying."""

COMMON_DOMAIN_ALIASES = {
    "youtube": "youtube.com",
    "google": "google.com",
    "instagram": "instagram.com",
    "tiktok": "tiktok.com",
    "twitter": "twitter.com",
    "reddit": "reddit.com",
    "github": "github.com",
}

MULTI_LABEL_SUFFIXES = {
    "co.uk",
    "org.uk",
    "gov.uk",
    "ac.uk",
    "com.au",
    "net.au",
    "org.au",
    "co.jp",
    "com.br",
    "com.mx",
}


def _registrable_domain(host: str) -> str:
    labels = [label for label in host.split(".") if label]
    if len(labels) < 2:
        return host
    suffix = ".".join(labels[-2:])
    if suffix in MULTI_LABEL_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def normalize_domain(raw: str) -> str:
    text = (raw or "").strip().lower()
    if not text:
        return ""

    text = text.replace(" dot ", ".").replace("[dot]", ".").replace("(dot)", ".")
    candidate = text if "://" in text or text.startswith("//") else f"//{text}"
    parsed = urlsplit(candidate)
    host = (parsed.hostname or parsed.path or "").strip().lower()
    host = host.split("/")[0].split("?")[0].split("#")[0]
    host = re.sub(r"[^a-z0-9.\-]", "", host).strip(".")
    if not host:
        return ""

    if "." not in host and host in COMMON_DOMAIN_ALIASES:
        return COMMON_DOMAIN_ALIASES[host]

    if host.startswith("www."):
        host = host[4:]

    if "." in host:
        host = _registrable_domain(host)

    return host


def get_blocked_domains() -> list[str]:
    db = SessionLocal()
    try:
        return [row.domain for row in db.query(Blocklist).order_by(Blocklist.domain.asc()).all()]
    finally:
        db.close()


def get_allowed_domains() -> list[str]:
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        rows = (
            db.query(Allowlist)
            .filter((Allowlist.expires_at.is_(None)) | (Allowlist.expires_at > now))
            .order_by(Allowlist.domain.asc())
            .all()
        )
        return [row.domain for row in rows]
    finally:
        db.close()


def restart_dnsmasq() -> bool:
    try:
        result = subprocess.run(
            ["sudo", "-n", "systemctl", "restart", "dnsmasq"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            log.info("dnsmasq restarted successfully")
            return True
        log.error(
            "dnsmasq restart failed (exit %d): %s",
            result.returncode,
            (result.stderr or result.stdout).strip(),
        )
        return False
    except Exception as exc:
        log.error("dnsmasq restart error: %s", exc)
        return False


def _write_dns_file(path: str, lines: list[str]) -> None:
    with open(path, "w") as handle:
        handle.writelines(lines)


def _render_blocklist_lines(domains: list[str]) -> list[str]:
    lines: list[str] = []
    for domain in sorted({domain for domain in domains if domain}):
        lines.append(f"address=/{domain}/0.0.0.0\n")
        lines.append(f"address=/{domain}/::\n")
    return lines


def _render_allowlist_lines(domains: list[str]) -> list[str]:
    return [f"server=/{domain}/#\n" for domain in sorted({domain for domain in domains if domain})]


def _prune_expired_allowlist(db) -> None:
    now = datetime.now(timezone.utc)
    expired = (
        db.query(Allowlist)
        .filter(Allowlist.expires_at.isnot(None), Allowlist.expires_at <= now)
        .all()
    )
    for entry in expired:
        db.delete(entry)
    if expired:
        db.commit()


def sync_dns_state() -> bool:
    db = SessionLocal()
    try:
        _prune_expired_allowlist(db)
        blocked = [row.domain for row in db.query(Blocklist).all()]
        allowed = [row.domain for row in db.query(Allowlist).all()]
    finally:
        db.close()

    allowed_set = set(allowed)
    effective_blocked = [domain for domain in blocked if domain not in allowed_set]

    try:
        _write_dns_file(DNS_BLOCKLIST_PATH, _render_blocklist_lines(effective_blocked))
        _write_dns_file(DNS_ALLOWLIST_PATH, _render_allowlist_lines(allowed))
    except OSError as exc:
        log.error("Failed to sync DNS files: %s", exc)
        return False

    restarted = restart_dnsmasq()
    log.info(
        "DNS state synchronized (blocked=%d, allowed=%d, effective_blocked=%d)",
        len(blocked),
        len(allowed),
        len(effective_blocked),
    )
    return restarted


def add_domain_to_dns_blocklist(domain: str) -> None:
    normalized = normalize_domain(domain)
    if not normalized:
        raise ValueError("invalid domain")
    if not sync_dns_state():
        raise RuntimeError("failed to sync dnsmasq state")
    log.info("Added %s to DNS blocklist", normalized)


def remove_domain_from_dns_blocklist(domain: str) -> None:
    normalized = normalize_domain(domain)
    if not normalized:
        raise ValueError("invalid domain")
    if not sync_dns_state():
        raise RuntimeError("failed to sync dnsmasq state")
    log.info("Removed %s from DNS blocklist", normalized)


async def update_dns_allowlist(domain: str, duration_minutes: int) -> None:
    normalized = normalize_domain(domain)
    if not normalized:
        raise ValueError("invalid domain")

    _add_to_db_allowlist(normalized, duration_minutes)
    if not sync_dns_state():
        raise RuntimeError("failed to sync dnsmasq state")
    log.info("DNS allowlist updated: %s (duration=%d min)", normalized, duration_minutes)

    if duration_minutes > 0:
        loop = asyncio.get_running_loop()
        loop.call_later(
            duration_minutes * 60,
            lambda: asyncio.create_task(_remove_domain(normalized)),
        )


def _add_to_db_allowlist(domain: str, duration_minutes: int) -> None:
    normalized = normalize_domain(domain)
    if not normalized:
        raise ValueError("invalid domain")

    db = SessionLocal()
    try:
        existing = db.query(Allowlist).filter_by(domain=normalized).first()
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=duration_minutes) if duration_minutes > 0 else None

        if existing:
            existing.granted_at = now
            existing.expires_at = expires
            existing.reason = "Argument accepted"
        else:
            db.add(
                Allowlist(
                    domain=normalized,
                    granted_at=now,
                    expires_at=expires,
                    reason="Argument accepted",
                )
            )
        db.commit()
    except Exception:
        log.exception("Failed to update allowlist in DB")
        raise
    finally:
        db.close()


async def _remove_domain(domain: str) -> None:
    normalized = normalize_domain(domain)
    if not normalized:
        return

    log.info("Access expired for %s - removing from allowlist", normalized)

    db = SessionLocal()
    try:
        entry = db.query(Allowlist).filter_by(domain=normalized).first()
        if entry:
            db.delete(entry)
            db.commit()
    except Exception:
        log.exception("Failed to remove %s from DB allowlist", normalized)
    finally:
        db.close()

    sync_dns_state()
    _log_event("site_expired", f"domain={normalized}")


async def evaluate_argument(domain: str, argument: str, study_stats: dict) -> dict:
    normalized = normalize_domain(domain)
    study_min = int(study_stats.get("study_seconds", 0)) // 60
    distracted_min = int(study_stats.get("distracted_seconds", 0)) // 60

    user_msg = (
        f"Domain requested: {normalized or domain}\n"
        f"Child's argument: \"{argument}\"\n"
        f"Study time today: {study_min} minutes\n"
        f"Distracted time today: {distracted_min} minutes"
    )

    _log_event("site_argument", f"domain={normalized or domain} | argument={argument}")

    try:
        raw = await asyncio.to_thread(_call_openai_argue, user_msg)
        decision = _parse_decision(raw)
    except Exception:
        log.exception("Argument evaluation failed")
        decision = {
            "decision": "deny",
            "reason": "Evaluation error - defaulting to deny",
            "duration_minutes": 0,
        }

    event_type = "site_granted" if decision["decision"] == "grant" else "site_denied"
    detail = (
        f"domain={normalized or domain} | reason={decision['reason']} | "
        f"mins={decision['duration_minutes']}"
    )
    _log_event(event_type, detail)
    return decision


def _call_openai_argue(user_msg: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=200,
        temperature=0.3,
        messages=[
            {"role": "system", "content": ARGUE_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )
    return response.choices[0].message.content.strip()


def _parse_decision(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        log.warning("Could not parse GPT response as JSON: %s", raw)
        return {
            "decision": "deny",
            "reason": "Malformed AI response - defaulting to deny",
            "duration_minutes": 0,
        }

    decision = "grant" if str(data.get("decision", "")).lower() == "grant" else "deny"
    reason = str(data.get("reason", "No reason provided"))
    try:
        duration = max(0, min(60, int(data.get("duration_minutes", 0))))
    except (TypeError, ValueError):
        duration = 0

    if decision == "deny":
        duration = 0

    return {"decision": decision, "reason": reason, "duration_minutes": duration}


def _log_event(event_type: str, detail: str | None = None) -> None:
    db = SessionLocal()
    try:
        db.add(Event(event_type=event_type, detail=detail))
        db.commit()
    except Exception:
        log.exception("Failed to log event %s", event_type)
    finally:
        db.close()
