import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    create_engine,
    event,
)
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./studyguard.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA journal_mode=WAL"))

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

def _utcnow():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    start_time = Column(DateTime, default=_utcnow, nullable=False)
    end_time = Column(DateTime, nullable=True)
    total_study_seconds = Column(Integer, default=0, nullable=False)
    total_distracted_seconds = Column(Integer, default=0, nullable=False)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=_utcnow, nullable=False)
    event_type = Column(String, nullable=False)
    detail = Column(String, nullable=True)


class Allowlist(Base):
    __tablename__ = "allowlist"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String, unique=True, nullable=False)
    granted_at = Column(DateTime, default=_utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    reason = Column(String, nullable=False)


class Blocklist(Base):
    __tablename__ = "blocklist"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String, unique=True, nullable=False)
    added_at = Column(DateTime, default=_utcnow, nullable=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEFAULT_BLOCKED = [
    "youtube.com",
    "instagram.com",
    "tiktok.com",
    "twitter.com",
    "reddit.com",
]


def init_db():
    """Create all tables and seed the default blocklist."""
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        for domain in DEFAULT_BLOCKED:
            exists = db.query(Blocklist).filter_by(domain=domain).first()
            if not exists:
                db.add(Blocklist(domain=domain))
        db.commit()
    finally:
        db.close()


def get_db():
    """FastAPI dependency that yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
