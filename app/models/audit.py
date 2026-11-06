"""Audit trail for privileged actions."""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin, fk_column, pk_column


class AuditLog(TimestampMixin, db.Model):
    __tablename__ = "audit_log"

    id = pk_column()
    actor_id = fk_column("users", nullable=True, ondelete="SET NULL")
    action = db.Column(db.String(60), nullable=False, index=True)
    target_type = db.Column(db.String(40))
    target_id = db.Column(db.String(64))
    meta = db.Column(db.JSON, default=dict)
    ip_address = db.Column(db.String(45))

    actor = db.relationship("User")

    __table_args__ = (db.Index("ix_audit_actor_created", "actor_id", "created_at"),)
