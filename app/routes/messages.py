"""Member-to-member messaging."""

from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import User
from app.services import messaging_service
from app.services.errors import DomainError

bp = Blueprint("messages", __name__, url_prefix="/messages")


@bp.get("/")
@login_required
def inbox():
    threads = messaging_service.list_threads(current_user)
    active_id = request.args.get("thread")
    active = None
    if active_id:
        try:
            active = messaging_service.get_thread(current_user, active_id)
        except DomainError:
            abort(404)
    elif threads:
        active = threads[0]
    if active is not None:
        messaging_service.mark_read(current_user, active)
        db.session.expire_all()
    return render_template(
        "pages/messages.html",
        threads=threads,
        active=active,
        unread_in_thread=messaging_service.unread_in_thread,
        last_message=messaging_service.last_message,
    )


@bp.get("/<thread_id>")
@login_required
def thread(thread_id: str):
    return redirect(url_for("messages.inbox", thread=thread_id))


@bp.post("/start/<user_id>")
@login_required
def start(user_id: str):
    target = db.session.get(User, user_id)
    if target is None:
        abort(404)
    try:
        thread = messaging_service.get_or_create_thread(current_user, target)
    except DomainError as exc:
        flash(getattr(exc, "message", "تعذّر بدء المحادثة."), "error")
        return redirect(url_for("profiles.public_profile", user_id=user_id))
    return redirect(url_for("messages.inbox", thread=thread.id))


@bp.post("/<thread_id>/send")
@login_required
def send(thread_id: str):
    try:
        messaging_service.send(current_user, thread_id, request.form.get("body", ""))
    except DomainError as exc:
        flash(getattr(exc, "message", "تعذّر إرسال الرسالة."), "error")
        return redirect(url_for("messages.inbox", thread=thread_id))
    return redirect(url_for("messages.inbox", thread=thread_id))
