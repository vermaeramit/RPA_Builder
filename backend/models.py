"""SQLAlchemy ORM models for the RPA Builder.

Three tables:
  workflows  - saved flow graphs
  runs       - run history (status, timing, full log, final variables)
  schedules  - display metadata for scheduled workflows (the APScheduler job
               store keeps its own `apscheduler_jobs` table for the triggers)

JSON columns use Postgres JSONB (falls back to generic JSON on other engines,
so the same models run against SQLite for tests).
"""
from __future__ import annotations

import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# JSONB on Postgres, plain JSON elsewhere.
JSONType = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    pass


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="Untitled")
    graph: Mapped[dict] = mapped_column(JSONType, default=dict)
    updated: Mapped[int] = mapped_column(BigInteger, default=0)
    owner_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workflow_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    workflow_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="success")  # success | failed
    trigger: Mapped[str] = mapped_column(String(16), default="manual")  # manual | schedule
    started: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    finished: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    logs: Mapped[list] = mapped_column(JSONType, default=list)
    variables: Mapped[dict] = mapped_column(JSONType, default=dict)
    owner_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)


class Schedule(Base):
    __tablename__ = "schedules"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(255))
    cron: Mapped[str] = mapped_column(String(128))
    owner_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    username: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="viewer")  # viewer | editor | admin
    created: Mapped[int] = mapped_column(BigInteger, default=0)
