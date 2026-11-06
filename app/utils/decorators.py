"""Route-level authorization decorators.

These are the *first* gate; services re-check ownership so no route can bypass it.
"""

from __future__ import annotations

from functools import wraps

from flask import abort
from flask_login import current_user


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles: str):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles and not current_user.is_admin:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def employer_required(view):
    return role_required("employer", "admin")(view)


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped
