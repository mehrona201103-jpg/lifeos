from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool
from app.config import settings
import logging
import os

logger = logging.getLogger("lifeos.db")

_tables_ready = False


def get_database_url() -> str:
    # Prefer raw env (Railway injects this) over cached settings
    url = (os.environ.get("DATABASE_URL") or settings.DATABASE_URL or "").strip()
    if not url:
        url = "sqlite:///./lifeos.db"
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


def _build_engine():
    url = get_database_url()
    dialect = url.split(":")[0] if url else "unknown"
    logger.info("DB dialect: %s", dialect)

    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )

    # PostgreSQL (Railway)
    # Don't force sslmode if already in URL; Railway internal often works without
    connect_args = {}
    if "sslmode=" not in url:
        # try require — if it fails at runtime, user can set DATABASE_SSL=disable
        ssl = os.environ.get("DATABASE_SSL", "require")
        if ssl and ssl != "disable":
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}sslmode={ssl}"

    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=5,
        pool_recycle=300,
        echo=False,
        connect_args=connect_args,
    )


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_tables() -> bool:
    """Create all tables if they don't exist. Safe to call multiple times."""
    global _tables_ready
    if _tables_ready:
        return True
    try:
        # Import models so metadata is filled
        from app.database import models  # noqa: F401

        Base.metadata.create_all(bind=engine)
        # Verify users table exists
        insp = inspect(engine)
        tables = insp.get_table_names()
        logger.info("DB tables: %s", tables)
        if "users" in tables:
            _tables_ready = True
            return True
        logger.error("users table missing after create_all")
        return False
    except Exception as e:
        logger.exception("ensure_tables failed: %s", e)
        return False


def check_db_connection() -> dict:
    """Return status dict for health checks."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        ok_tables = ensure_tables()
        return {"ok": True, "tables": ok_tables}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
