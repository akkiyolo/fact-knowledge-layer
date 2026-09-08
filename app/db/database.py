"""
Database connection and session management.
Connects exclusively to Render PostgreSQL via DATABASE_URL.
Never logs credentials.
"""

import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from app.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""
    pass


# ── Engine & Session Factory ─────────────────────────────────

_engine = None
_SessionLocal = None


def get_engine():
    """Create or return the cached SQLAlchemy engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        logger.info("Connecting to database at %s", settings.database_url_safe)
        _engine = create_engine(
            settings.database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,
            echo=settings.debug,
        )
    return _engine


def get_session_factory() -> sessionmaker:
    """Get the session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


def get_db() -> Session:
    """FastAPI dependency: yield a database session."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


# ── Health Check ─────────────────────────────────────────────

def check_database_health() -> dict:
    """
    Verify database connectivity and pgvector availability.
    Returns a health status dict. Never exposes credentials.
    """
    result = {
        "status": "unhealthy",
        "database": "unreachable",
        "pgvector": "unknown",
    }
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            result["database"] = "connected"
            result["status"] = "healthy"

            # Check pgvector
            try:
                conn.execute(text("SELECT 'vector'::regtype"))
                result["pgvector"] = "available"
            except Exception:
                result["pgvector"] = "not_available"

    except Exception as e:
        # Never expose connection string or credentials
        error_msg = str(e)
        # Sanitize: remove anything that looks like a connection string
        if "@" in error_msg:
            error_msg = "Database connection failed (credentials hidden)"
        result["error"] = error_msg
        logger.error("Database health check failed: %s", error_msg)

    return result


# ── pgvector Setup ───────────────────────────────────────────

def ensure_pgvector(engine=None):
    """Enable pgvector extension if available. Fails clearly if not."""
    if engine is None:
        engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
            logger.info("pgvector extension enabled")
    except Exception as e:
        error_msg = str(e)
        if "@" in error_msg:
            error_msg = "pgvector setup failed (credentials hidden)"
        logger.error("Failed to enable pgvector: %s", error_msg)
        raise RuntimeError(
            "pgvector extension is required but could not be enabled. "
            "Ensure your Render PostgreSQL plan supports pgvector."
        ) from e


def init_db():
    """Initialize the database: enable pgvector and create all tables."""
    engine = get_engine()
    ensure_pgvector(engine)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")
