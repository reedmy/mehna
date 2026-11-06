"""Append-only audit log for privileged actions."""

from __future__ import annotations

from flask import request

from app.extensions import db
from app.models import AuditLog, User


def log(
    actor: User | None,
    action: str,
    *,
    target_type: str | None = None,
    target_id: str | None = None,
    **meta,
) -> None:
    db.session.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id else None,
            meta=meta or {},
            ip_address=(request.remote_addr if request else None),
        )
    )
    db.session.commit()
