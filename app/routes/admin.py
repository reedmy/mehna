"""Admin console: moderation, users, jobs, reports, audit."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_

from app.extensions import db
from app.models import Application, AuditLog, Company, Job, JobReport, User
from app.models.enums import (
    JOB_STATUS_LABELS,
    VERIFICATION_LABELS,
    JobStatus,
    ReportStatus,
    VerificationStatus,
)
from app.services import audit_service, companies_service
from app.utils.decorators import admin_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("/")
@login_required
@admin_required
def dashboard():
    stats = {
        "users": db.session.scalar(db.select(func.count(User.id))) or 0,
        "employers": db.session.scalar(
            db.select(func.count(User.id)).where(User.role == "employer")
        )
        or 0,
        "companies": db.session.scalar(db.select(func.count(Company.id))) or 0,
        "pending_companies": db.session.scalar(
            db.select(func.count(Company.id)).where(
                Company.verification_status == VerificationStatus.PENDING.value
            )
        )
        or 0,
        "published_jobs": db.session.scalar(
            db.select(func.count(Job.id)).where(Job.status == JobStatus.PUBLISHED.value)
        )
        or 0,
        "applications": db.session.scalar(db.select(func.count(Application.id))) or 0,
        "open_reports": db.session.scalar(
            db.select(func.count(JobReport.id)).where(JobReport.status == ReportStatus.OPEN.value)
        )
        or 0,
    }
    pending = list(
        db.session.scalars(
            db.select(Company)
            .where(Company.verification_status == VerificationStatus.PENDING.value)
            .order_by(Company.updated_at.desc())
            .limit(8)
        )
    )
    reports = list(
        db.session.scalars(
            db.select(JobReport)
            .where(JobReport.status == ReportStatus.OPEN.value)
            .order_by(JobReport.created_at.desc())
            .limit(6)
        )
    )
    recent_users = list(
        db.session.scalars(db.select(User).order_by(User.created_at.desc()).limit(6))
    )
    return render_template(
        "pages/admin_dashboard.html",
        stats=stats,
        pending=pending,
        reports=reports,
        recent_users=recent_users,
    )


@bp.get("/companies")
@login_required
@admin_required
def companies():
    status = request.args.get("status") or None
    q = (request.args.get("q") or "").strip()
    stmt = db.select(Company).order_by(Company.created_at.desc())
    if status:
        stmt = stmt.where(Company.verification_status == status)
    if q:
        stmt = stmt.where(or_(Company.name.ilike(f"%{q}%"), Company.city.ilike(f"%{q}%")))
    pagination = db.paginate(
        stmt, page=request.args.get("page", 1, type=int), per_page=20, error_out=False
    )
    return render_template(
        "pages/admin_companies.html",
        pagination=pagination,
        active_status=status,
        q=q,
        status_labels=VERIFICATION_LABELS,
    )


@bp.post("/companies/<company_id>/verify")
@login_required
@admin_required
def company_verify(company_id: str):
    company = db.session.get(Company, company_id)
    if company is None:
        flash("الشركة غير موجودة.", "error")
        return redirect(url_for("admin.companies"))
    companies_service.verify(current_user, company)
    audit_service.log(current_user, "company.verified", target_type="company", target_id=company.id)
    flash(f"تم توثيق «{company.name}».", "success")
    return redirect(request.referrer or url_for("admin.companies"))


@bp.post("/companies/<company_id>/reject")
@login_required
@admin_required
def company_reject(company_id: str):
    company = db.session.get(Company, company_id)
    if company is None:
        flash("الشركة غير موجودة.", "error")
        return redirect(url_for("admin.companies"))
    companies_service.reject(current_user, company, request.form.get("reason"))
    audit_service.log(
        current_user,
        "company.rejected",
        target_type="company",
        target_id=company.id,
        reason=request.form.get("reason"),
    )
    flash(f"تم رفض توثيق «{company.name}».", "info")
    return redirect(request.referrer or url_for("admin.companies"))


@bp.get("/users")
@login_required
@admin_required
def users():
    role = request.args.get("role") or None
    q = (request.args.get("q") or "").strip()
    stmt = db.select(User).order_by(User.created_at.desc())
    if role:
        stmt = stmt.where(User.role == role)
    if q:
        stmt = stmt.where(or_(User.email.ilike(f"%{q}%"), User.full_name.ilike(f"%{q}%")))
    pagination = db.paginate(
        stmt, page=request.args.get("page", 1, type=int), per_page=20, error_out=False
    )
    return render_template("pages/admin_users.html", pagination=pagination, active_role=role, q=q)


@bp.post("/users/<user_id>/toggle")
@login_required
@admin_required
def user_toggle(user_id: str):
    user = db.session.get(User, user_id)
    if user is None:
        flash("المستخدم غير موجود.", "error")
    elif user.id == current_user.id:
        flash("لا يمكنك تعطيل حسابك.", "error")
    else:
        user.is_active = not user.is_active
        db.session.commit()
        audit_service.log(
            current_user,
            "user.toggled",
            target_type="user",
            target_id=user.id,
            active=user.is_active,
        )
        flash("تم تحديث حالة الحساب.", "success")
    return redirect(request.referrer or url_for("admin.users"))


@bp.get("/jobs")
@login_required
@admin_required
def jobs():
    status = request.args.get("status") or None
    stmt = db.select(Job).order_by(Job.created_at.desc())
    if status:
        stmt = stmt.where(Job.status == status)
    pagination = db.paginate(
        stmt, page=request.args.get("page", 1, type=int), per_page=20, error_out=False
    )
    return render_template(
        "pages/admin_jobs.html",
        pagination=pagination,
        active_status=status,
        status_labels=JOB_STATUS_LABELS,
    )


@bp.get("/reports")
@login_required
@admin_required
def reports():
    stmt = (
        db.select(JobReport)
        .where(JobReport.status == ReportStatus.OPEN.value)
        .order_by(JobReport.created_at.desc())
    )
    rows = list(db.session.scalars(stmt))
    return render_template("pages/admin_reports.html", reports=rows)


@bp.post("/reports/<report_id>/resolve")
@login_required
@admin_required
def report_resolve(report_id: str):
    report = db.session.get(JobReport, report_id)
    if report is None:
        flash("البلاغ غير موجود.", "error")
        return redirect(url_for("admin.reports"))
    action = request.form.get("action", "dismissed")
    report.status = (
        ReportStatus.ACTIONED.value if action == "action" else ReportStatus.DISMISSED.value
    )
    report.resolution_note = (request.form.get("note") or "").strip()[:1000] or None
    if action == "action" and report.job:
        report.job.status = JobStatus.CLOSED.value
    db.session.commit()
    audit_service.log(
        current_user, f"report.{report.status}", target_type="job", target_id=report.job_id
    )
    flash("تمت معالجة البلاغ.", "success")
    return redirect(url_for("admin.reports"))


@bp.get("/audit")
@login_required
@admin_required
def audit():
    rows = list(
        db.session.scalars(db.select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100))
    )
    return render_template("pages/admin_audit.html", rows=rows)
