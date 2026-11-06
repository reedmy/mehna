"""Direct messages between platform members (no external dependency)."""

from __future__ import annotations

from sqlalchemy import func, or_

from app.extensions import db
from app.models import Message, MessageThread, User, utcnow
from app.models.enums import NotificationType
from app.services import notifications_service, profiles_service
from app.services.errors import NotFound, PermissionDenied, ValidationError


def _ordered_ids(first: str, second: str) -> tuple[str, str]:
    return (first, second) if first < second else (second, first)


def get_or_create_thread(first: User, second: User) -> MessageThread:
    if first.id == second.id:
        raise ValidationError("لا يمكنك مراسلة نفسك.")
    if not second.is_active:
        raise ValidationError("هذا الحساب غير متاح.")
    if not profiles_service.can_message(first, second):
        raise PermissionDenied("هذا المستخدم لا يستقبل الرسائل حاليًا.")
    a, b = _ordered_ids(first.id, second.id)
    thread = db.session.scalar(
        db.select(MessageThread).filter_by(user_a_id=a, user_b_id=b)
    )
    if thread is None:
        thread = MessageThread(user_a_id=a, user_b_id=b)
        db.session.add(thread)
        db.session.commit()
    return thread


def get_thread(actor: User, thread_id: str) -> MessageThread:
    thread = db.session.get(MessageThread, thread_id)
    if thread is None:
        raise NotFound("المحادثة غير موجودة.")
    if actor.id not in (thread.user_a_id, thread.user_b_id) and not actor.is_admin:
        raise PermissionDenied()
    return thread


def list_threads(actor: User) -> list[MessageThread]:
    return list(
        db.session.scalars(
            db.select(MessageThread)
            .where(or_(MessageThread.user_a_id == actor.id, MessageThread.user_b_id == actor.id))
            .order_by(MessageThread.last_message_at.desc().nullslast())
        )
    )


def send(actor: User, thread_id: str | None, body: str, recipient_id: str | None = None):
    text = (body or "").strip()
    if len(text) < 1:
        raise ValidationError("اكتب رسالة أولًا.")
    if len(text) > 4000:
        raise ValidationError("الرسالة طويلة جدًا (4000 حرف كحد أقصى).")

    if thread_id:
        thread = get_thread(actor, thread_id)
    elif recipient_id:
        recipient = db.session.get(User, recipient_id)
        if recipient is None:
            raise NotFound("المستخدم غير موجود.")
        thread = get_or_create_thread(actor, recipient)
    else:
        raise ValidationError("اختر محادثة أو مستلمًا.")

    recipient = thread.other_user(actor.id)
    message = Message(thread_id=thread.id, sender_id=actor.id, body=text)
    thread.last_message_at = utcnow()
    db.session.add(message)
    notifications_service.notify(
        recipient,
        type=NotificationType.SYSTEM.value,
        title=f"رسالة جديدة من {actor.full_name}",
        body=text[:180],
        link=f"/messages/{thread.id}",
        commit=False,
    )
    db.session.commit()
    return message


def mark_read(actor: User, thread: MessageThread) -> None:
    db.session.execute(
        db.update(Message)
        .where(Message.thread_id == thread.id)
        .where(Message.sender_id != actor.id)
        .where(Message.is_read.is_(False))
        .values(is_read=True)
    )
    db.session.commit()


def unread_count(actor: User) -> int:
    return (
        db.session.scalar(
            db.select(func.count(Message.id))
            .join(MessageThread, Message.thread_id == MessageThread.id)
            .where(
                or_(
                    MessageThread.user_a_id == actor.id,
                    MessageThread.user_b_id == actor.id,
                )
            )
            .where(Message.sender_id != actor.id)
            .where(Message.is_read.is_(False))
        )
        or 0
    )


def last_message(thread: MessageThread) -> Message | None:
    return thread.messages[-1] if thread.messages else None


def unread_in_thread(actor: User, thread: MessageThread) -> int:
    return sum(
        1 for message in thread.messages if message.sender_id != actor.id and not message.is_read
    )
