"""Shared model helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Uuid

from app.extensions import db


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def pk_column():
    """Portable UUID primary key: native uuid on PostgreSQL, CHAR(32) on SQLite."""
    return db.Column(Uuid(as_uuid=False), primary_key=True, default=new_id)


def fk_column(table: str, *, nullable: bool = False, ondelete: str = "CASCADE"):
    return db.Column(
        Uuid(as_uuid=False),
        db.ForeignKey(f"{table}.id", ondelete=ondelete),
        nullable=nullable,
    )


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
