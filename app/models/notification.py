"""In-app notifications (polled by HTMX — no websocket dependency)."""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin, fk_column, pk_column
from app.models.enums import NotificationType


class Notification(TimestampMixin, db.Model):
    __tablename__ = "notifications"

    id = pk_column()
    user_id = fk_column("users", nullable=False, ondelete="CASCADE")
    type = db.Column(db.String(40), nullable=False, default=NotificationType.SYSTEM.value)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.String(500))
    link = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, nullable=False, default=False, index=True)

    user = db.relationship("User", back_populates="notifications")

    __table_args__ = (db.Index("ix_notifications_user_unread", "user_id", "is_read"),)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Notification {self.title}>"
