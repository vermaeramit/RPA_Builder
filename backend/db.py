"""Database engine and session factory (SQLAlchemy + Postgres).

The connection string is read from the DATABASE_URL environment variable
(or a local .env file). A plain `postgresql://` URL is upgraded to the
psycopg3 driver, which is what we install.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy backend/.env.example to backend/.env "
        "and point it at your Postgres database."
    )

# Make sure we use the installed psycopg (v3) driver.
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_db() -> None:
    """Create tables if they don't exist yet, then apply lightweight migrations."""
    from models import Base  # imported here to avoid a circular import

    Base.metadata.create_all(engine)
    _migrate()


def _migrate() -> None:
    """Idempotent column additions for tables that predate a schema change.

    create_all() never alters existing tables, so we add new columns here. Only
    needed on Postgres; on a fresh SQLite (tests) create_all already has them.
    """
    if engine.dialect.name != "postgresql":
        return
    stmts = [
        "ALTER TABLE workflows ADD COLUMN IF NOT EXISTS owner_id VARCHAR(32)",
        "ALTER TABLE runs ADD COLUMN IF NOT EXISTS owner_id VARCHAR(32)",
        "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS owner_id VARCHAR(32)",
    ]
    with engine.begin() as conn:
        for s in stmts:
            conn.execute(text(s))
