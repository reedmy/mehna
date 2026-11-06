"""In-app notifications."""

from __future__ import annotations

from app.extensions import db
from app.models import Notification, User
from app.models.enums import NotificationType


def notify(
    user: User | None,
    *,
    type: str = NotificationType.SYSTEM.value,
    title: str,
    body: str | None = None,
    link: str | None = None,
    commit: bool = True,
) -> Notification | None:
    if user is None:
        return None
    item = Notification(
        user_id=user.id, type=type, title=title[:160], body=(body or "")[:500], link=link
    )
    db.session.add(item)
    if commit:
        db.session.commit()
    return item


def list_for(user: User, limit: int = 15) -> list[Notification]:
    return list(
        db.session.scalars(
            db.select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
    )


def unread_count(user: User) -> int:
    return (
        db.session.scalar(
            db.select(db.func.count(Notification.id))
            .where(Notification.user_id == user.id)
            .where(Notification.is_read.is_(False))
        )
        or 0
    )


def mark_all_read(user: User) -> None:
    db.session.execute(
        db.update(Notification)
        .where(Notification.user_id == user.id)
        .where(Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.session.commit()


def mark_read(user: User, notification_id: str) -> None:
    db.session.execute(
        db.update(Notification)
        .where(Notification.id == notification_id)
        .where(Notification.user_id == user.id)
        .values(is_read=True)
    )
    db.session.commit()
