"""
database.py
-----------
SQLAlchemy engine + session factory + declarative Base.

Environment-aware:
  • Reads DATABASE_URL from the environment (or a .env file via python-dotenv).
  • Falls back to a local SQLite file for zero-config local development.
  • Enables connection-pool health checks (pool_pre_ping) for PostgreSQL
    so stale connections are automatically discarded after a DB restart.
  • connect_args only applied for SQLite — psycopg2 does not accept them.
"""

import os
import logging

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Load .env when present — no-op in production (env vars already set)
load_dotenv()

logger = logging.getLogger(__name__)

# ── Resolve DATABASE_URL ──────────────────────────────────────────────────────
# Priority: real env var → .env file → SQLite fallback
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./tasks.db")

_is_sqlite = DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    logger.info("Database backend: SQLite (%s)", DATABASE_URL)
else:
    _safe_url = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
    logger.info("Database backend: PostgreSQL (@%s)", _safe_url)

# ── Engine ────────────────────────────────────────────────────────────────────
# pool_pre_ping → probes each connection before use; transparently replaces
#                 stale ones after DB restarts. Essential for Render/Docker.
# connect_args  → SQLite only: allows multi-thread access from FastAPI workers.
# pool_size / max_overflow / pool_recycle → PostgreSQL only; bounded, healthy pool.

_engine_kwargs: dict = {"pool_pre_ping": True}

if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_size"]    = 5
    _engine_kwargs["max_overflow"] = 10
    _engine_kwargs["pool_recycle"] = 1800  # recycle after 30 min to avoid idle timeouts

engine = create_engine(DATABASE_URL, **_engine_kwargs)

# ── Session factory ───────────────────────────────────────────────────────────
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ── Declarative Base ──────────────────────────────────────────────────────────
Base = declarative_base()


# ── FastAPI dependency ────────────────────────────────────────────────────────
def get_db():
    """
    Yields a database session per request and guarantees cleanup.
    Rolls back on any unhandled exception so the connection is returned
    to the pool in a clean state.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
