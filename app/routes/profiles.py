"""Public professional profiles and protected upload delivery."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, abort, redirect, render_template, send_file
from flask_login import current_user

from app.extensions import db
from app.models import Application, Company, User
from app.models.enums import LANGUAGE_PROFICIENCY_LABELS, SKILL_LEVEL_LABELS
from app.services import profiles_service
from app.services.errors import ValidationError

bp = Blueprint("profiles", __name__)


@bp.get("/u/<user_id>")
def public_profile(user_id: str):
    user = db.session.get(User, user_id)
    if user is None or not user.is_active:
        abort(404)

    viewer = current_user if current_user.is_authenticated else None
    flags = profiles_service.viewer_flags(user, viewer)
    company = None
    if user.role == "employer":
        company = db.session.scalar(
            db.select(Company).where(Company.owner_id == user.id).order_by(Company.created_at)
        )

    applications_count = None
    if viewer is not None and (viewer.id == user.id or viewer.is_admin):
        applications_count = db.session.scalar(
            db.select(db.func.count(Application.id)).where(Application.seeker_id == user.id)
        )

    return render_template(
        "pages/public_profile.html",
        profile_user=user,
        profile=user.profile,
        company=company,
        flags=flags,
        applications_count=applications_count,
        skill_levels=SKILL_LEVEL_LABELS,
        language_levels=LANGUAGE_PROFICIENCY_LABELS,
    )


@bp.get("/media/avatar/<user_id>")
def avatar(user_id: str):
    user = db.session.get(User, user_id)
    if user is None or not user.is_active:
        abort(404)
    profile = user.profile
    if profile and profile.avatar_path:
        try:
            path = profiles_service.disk_path(profile.avatar_path)
        except ValidationError:
            abort(404)
        if path.is_file():
            response = send_file(path, mimetype="image/jpeg", max_age=3600)
            response.headers["Cache-Control"] = "public, max-age=3600"
            return response
    if user.avatar_url:
        return redirect(user.avatar_url)
    abort(404)


@bp.get("/media/cover/<user_id>")
def cover(user_id: str):
    user = db.session.get(User, user_id)
    if user is None or not user.is_active:
        abort(404)
    profile = user.profile
    if profile and profile.cover_path:
        try:
            path = profiles_service.disk_path(profile.cover_path)
        except ValidationError:
            abort(404)
        if path.is_file():
            response = send_file(path, mimetype="image/jpeg", max_age=3600)
            response.headers["Cache-Control"] = "public, max-age=3600"
            return response
    abort(404)


@bp.get("/media/cv/<user_id>")
def cv(user_id: str):
    user = db.session.get(User, user_id)
    if user is None or not user.is_active:
        abort(404)
    viewer = current_user if current_user.is_authenticated else None
    flags = profiles_service.viewer_flags(user, viewer)
    if not flags["cv"]:
        abort(403)
    profile = user.profile
    if profile is None or not profile.cv_path:
        abort(404)
    try:
        path = profiles_service.disk_path(profile.cv_path)
    except ValidationError:
        abort(404)
    if not path.is_file():
        abort(404)
    suffix = Path(path).suffix.lower()
    mimetypes = {
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    return send_file(
        path,
        mimetype=mimetypes.get(suffix, "application/octet-stream"),
        as_attachment=True,
        download_name=profile.cv_filename or f"cv-{user.full_name}{suffix}",
        max_age=0,
    )
