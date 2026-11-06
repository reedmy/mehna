"""Job-seeker area: dashboard, applications, saved jobs, profile manager."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Profile, SavedJob
from app.models.enums import (
    APPLICATION_STATUS_LABELS,
    APPLICATION_STATUS_TONE,
    CAREER_LEVEL_LABELS,
    CITIES,
    EMPLOYMENT_TYPE_LABELS,
    INDUSTRIES,
    LANGUAGE_PROFICIENCY_LABELS,
    PROFILE_SECTIONS,
    PROFILE_VISIBILITY_LABELS,
    SKILL_LEVEL_LABELS,
)
from app.services import (
    applications_service,
    auth_service,
    engagement_service,
    jobs_service,
    messaging_service,
    profiles_service,
)
from app.services.errors import ValidationError

bp = Blueprint("seeker", __name__, url_prefix="/dashboard")


@bp.get("/")
@login_required
def dashboard():
    if current_user.is_admin:
        return redirect(url_for("admin.dashboard"))
    if current_user.role == "employer":
        return redirect(url_for("employer.dashboard"))

    applications = applications_service.list_for_seeker(current_user)
    profile = profiles_service.get_or_create(current_user)
    saved_count = db.session.scalar(
        db.select(db.func.count(SavedJob.id)).where(SavedJob.user_id == current_user.id)
    )
    stats = {
        "applications": len(applications),
        "in_progress": sum(1 for a in applications if a.is_active),
        "interviews": sum(1 for a in applications if a.status == "interview"),
        "saved": saved_count or 0,
        "messages": messaging_service.unread_count(current_user),
    }
    recommended = jobs_service.recommended_for(current_user, limit=4)
    return render_template(
        "pages/seeker_dashboard.html",
        applications=applications[:5],
        stats=stats,
        profile=profile,
        recommended=recommended,
        status_labels=APPLICATION_STATUS_LABELS,
        status_tones=APPLICATION_STATUS_TONE,
    )


@bp.get("/applications")
@login_required
def applications():
    rows = applications_service.list_for_seeker(current_user)
    return render_template(
        "pages/seeker_applications.html", applications=rows, status_labels=APPLICATION_STATUS_LABELS
    )


@bp.post("/applications/<application_id>/withdraw")
@login_required
def withdraw(application_id: str):
    applications_service.withdraw(current_user, application_id)
    flash("تم سحب الطلب.", "info")
    return redirect(url_for("seeker.applications"))


@bp.get("/saved")
@login_required
def saved():
    rows = engagement_service.list_saved(current_user)
    return render_template("pages/seeker_saved.html", saved=rows)


# ── profile manager ─────────────────────────────────────


@bp.get("/profile")
@login_required
def profile():
    profile_row = profiles_service.get_or_create(current_user)
    return render_template(
        "pages/profile_manage.html",
        profile=profile_row,
        privacy=profiles_service.get_privacy(current_user),
        cities=CITIES,
        industries=INDUSTRIES,
        sections=PROFILE_SECTIONS,
        skill_levels=SKILL_LEVEL_LABELS,
        language_levels=LANGUAGE_PROFICIENCY_LABELS,
        employment_types=EMPLOYMENT_TYPE_LABELS,
        career_levels=CAREER_LEVEL_LABELS,
        visibilities=PROFILE_VISIBILITY_LABELS,
    )


def _profile_row() -> Profile:
    return profiles_service.get_or_create(current_user)


def _ok(message: str, anchor: str = "basic"):
    flash(message, "success")
    return redirect(url_for("seeker.profile", _anchor=anchor))


def _failure(exc: Exception, anchor: str = "basic"):
    db.session.rollback()
    flash(getattr(exc, "message", str(exc)), "error")
    return redirect(url_for("seeker.profile", _anchor=anchor))


@bp.post("/profile/basic")
@login_required
def profile_basic():
    try:
        profiles_service.update_basic(current_user, _profile_row(), request.form)
        return _ok("تم حفظ بيانات الملف الشخصي.", "basic")
    except ValidationError as exc:
        return _failure(exc, "basic")


@bp.post("/profile/privacy")
@login_required
def profile_privacy():
    profiles_service.update_privacy(current_user, request.form)
    return _ok("تم تحديث إعدادات الخصوصية.", "privacy")


@bp.post("/profile/avatar")
@login_required
def profile_avatar():
    try:
        profiles_service.save_avatar(current_user, _profile_row(), request.files.get("avatar"))
        return _ok("تم تحديث صورة الملف.", "basic")
    except ValidationError as exc:
        return _failure(exc, "basic")


@bp.post("/profile/avatar/remove")
@login_required
def profile_avatar_remove():
    profiles_service.remove_avatar(current_user, _profile_row())
    return _ok("تمت إزالة صورة الملف.", "basic")


@bp.post("/profile/cover")
@login_required
def profile_cover():
    try:
        profiles_service.save_cover(current_user, _profile_row(), request.files.get("cover"))
        return _ok("تم تحديث صورة الغلاف.", "basic")
    except ValidationError as exc:
        return _failure(exc, "basic")


@bp.post("/profile/cover/remove")
@login_required
def profile_cover_remove():
    profiles_service.remove_cover(current_user, _profile_row())
    return _ok("تمت إزالة صورة الغلاف.", "basic")


@bp.post("/profile/cv")
@login_required
def profile_cv():
    try:
        profiles_service.save_cv(current_user, _profile_row(), request.files.get("cv"))
        return _ok("تم رفع السيرة الذاتية.", "privacy")
    except ValidationError as exc:
        return _failure(exc, "privacy")


@bp.post("/profile/cv/remove")
@login_required
def profile_cv_remove():
    profiles_service.remove_cv(current_user, _profile_row())
    return _ok("تم حذف السيرة الذاتية المرفوعة.", "privacy")


# ── education ───────────────────────────────────────────


@bp.post("/profile/education")
@login_required
def education_create():
    try:
        profiles_service.add_education(current_user, _profile_row(), request.form)
        return _ok("تمت إضافة السجل التعليمي.", "education")
    except ValidationError as exc:
        return _failure(exc, "education")


@bp.post("/profile/education/<row_id>")
@login_required
def education_update(row_id: str):
    try:
        profiles_service.update_education(current_user, _profile_row(), row_id, request.form)
        return _ok("تم تحديث السجل التعليمي.", "education")
    except ValidationError as exc:
        return _failure(exc, "education")


@bp.post("/profile/education/<row_id>/delete")
@login_required
def education_delete(row_id: str):
    try:
        profiles_service.delete_education(current_user, _profile_row(), row_id)
        return _ok("تم حذف السجل التعليمي.", "education")
    except ValidationError as exc:
        return _failure(exc, "education")


# ── experience ──────────────────────────────────────────


@bp.post("/profile/experience")
@login_required
def experience_create():
    try:
        profiles_service.add_experience(current_user, _profile_row(), request.form)
        return _ok("تمت إضافة الخبرة العملية.", "experience")
    except ValidationError as exc:
        return _failure(exc, "experience")


@bp.post("/profile/experience/<row_id>")
@login_required
def experience_update(row_id: str):
    try:
        profiles_service.update_experience(current_user, _profile_row(), row_id, request.form)
        return _ok("تم تحديث الخبرة العملية.", "experience")
    except ValidationError as exc:
        return _failure(exc, "experience")


@bp.post("/profile/experience/<row_id>/delete")
@login_required
def experience_delete(row_id: str):
    try:
        profiles_service.delete_experience(current_user, _profile_row(), row_id)
        return _ok("تم حذف الخبرة العملية.", "experience")
    except ValidationError as exc:
        return _failure(exc, "experience")


# ── skills / languages ──────────────────────────────────


@bp.post("/profile/skills")
@login_required
def skill_create():
    try:
        profiles_service.add_skill(current_user, _profile_row(), request.form)
        return _ok("تمت إضافة المهارة.", "skills")
    except ValidationError as exc:
        return _failure(exc, "skills")


@bp.post("/profile/skills/<row_id>/delete")
@login_required
def skill_delete(row_id: str):
    try:
        profiles_service.delete_skill(current_user, _profile_row(), row_id)
        return _ok("تم حذف المهارة.", "skills")
    except ValidationError as exc:
        return _failure(exc, "skills")


@bp.post("/profile/languages")
@login_required
def language_create():
    try:
        profiles_service.add_language(current_user, _profile_row(), request.form)
        return _ok("تمت إضافة اللغة.", "skills")
    except ValidationError as exc:
        return _failure(exc, "skills")


@bp.post("/profile/languages/<row_id>/delete")
@login_required
def language_delete(row_id: str):
    try:
        profiles_service.delete_language(current_user, _profile_row(), row_id)
        return _ok("تم حذف اللغة.", "skills")
    except ValidationError as exc:
        return _failure(exc, "skills")


# ── certifications ──────────────────────────────────────


@bp.post("/profile/certifications")
@login_required
def certification_create():
    try:
        profiles_service.add_certification(current_user, _profile_row(), request.form)
        return _ok("تمت إضافة الشهادة.", "certifications")
    except ValidationError as exc:
        return _failure(exc, "certifications")


@bp.post("/profile/certifications/<row_id>")
@login_required
def certification_update(row_id: str):
    try:
        profiles_service.update_certification(
            current_user, _profile_row(), row_id, request.form
        )
        return _ok("تم تحديث الشهادة.", "certifications")
    except ValidationError as exc:
        return _failure(exc, "certifications")


@bp.post("/profile/certifications/<row_id>/delete")
@login_required
def certification_delete(row_id: str):
    try:
        profiles_service.delete_certification(current_user, _profile_row(), row_id)
        return _ok("تم حذف الشهادة.", "certifications")
    except ValidationError as exc:
        return _failure(exc, "certifications")


# ── projects ────────────────────────────────────────────


@bp.post("/profile/projects")
@login_required
def project_create():
    try:
        profiles_service.add_project(current_user, _profile_row(), request.form)
        return _ok("تمت إضافة المشروع.", "projects")
    except ValidationError as exc:
        return _failure(exc, "projects")


@bp.post("/profile/projects/<row_id>")
@login_required
def project_update(row_id: str):
    try:
        profiles_service.update_project(current_user, _profile_row(), row_id, request.form)
        return _ok("تم تحديث المشروع.", "projects")
    except ValidationError as exc:
        return _failure(exc, "projects")


@bp.post("/profile/projects/<row_id>/delete")
@login_required
def project_delete(row_id: str):
    try:
        profiles_service.delete_project(current_user, _profile_row(), row_id)
        return _ok("تم حذف المشروع.", "projects")
    except ValidationError as exc:
        return _failure(exc, "projects")


@bp.post("/password")
@login_required
def password():
    try:
        auth_service.change_password(
            current_user,
            current=request.form.get("current_password", ""),
            new=request.form.get("new_password", ""),
        )
        flash("تم تحديث كلمة المرور.", "success")
    except ValidationError as exc:
        flash(exc.message, "error")
    return redirect(url_for("seeker.profile"))
