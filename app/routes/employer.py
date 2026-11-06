"""Employer area: company profile, job CRUD, applicants."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Company, Job
from app.models.enums import (
    APPLICATION_STATUS_LABELS,
    CAREER_LEVEL_LABELS,
    CITIES,
    COMPANY_SIZES,
    INDUSTRIES,
    JOB_STATUS_LABELS,
    JOB_TYPE_LABELS,
    WORK_MODE_LABELS,
    JobStatus,
)
from app.services import applications_service, companies_service, jobs_service, plans_service
from app.services.errors import DomainError

bp = Blueprint("employer", __name__, url_prefix="/employer")


def _current_company() -> Company | None:
    return db.session.scalar(
        db.select(Company).where(Company.owner_id == current_user.id).order_by(Company.created_at)
    )


@bp.get("/")
@login_required
def dashboard():
    if current_user.is_admin:
        return redirect(url_for("admin.dashboard"))
    if current_user.role != "employer":
        return redirect(url_for("seeker.dashboard"))

    company = _current_company()
    if company is None:
        return render_template("pages/employer_onboarding.html")

    jobs = list(
        db.session.scalars(
            db.select(Job).where(Job.company_id == company.id).order_by(Job.created_at.desc())
        )
    )
    stats = jobs_service.employer_stats(company)
    recent = applications_service.list_for_company(current_user, company.id)[:6]
    limit = plans_service.limits(current_user.plan)["active_jobs"]
    used = plans_service.active_jobs_count(company)
    return render_template(
        "pages/employer_dashboard.html",
        company=company,
        jobs=jobs[:6],
        stats=stats,
        recent=recent,
        limit=limit,
        used=used,
        status_labels=APPLICATION_STATUS_LABELS,
        job_status_labels=JOB_STATUS_LABELS,
    )


@bp.route("/company", methods=["GET", "POST"])
@login_required
def company():
    if current_user.role != "employer" and not current_user.is_admin:
        return redirect(url_for("seeker.dashboard"))

    company = _current_company()
    if request.method == "POST":
        payload = {
            "name": request.form.get("name"),
            "description": request.form.get("description"),
            "website": request.form.get("website"),
            "city": request.form.get("city"),
            "industry": request.form.get("industry"),
            "size": request.form.get("size"),
        }
        if company is None:
            companies_service.create(current_user, payload)
            flash("تم إنشاء ملف الشركة. اطلب التوثيق لنشر الوظائف.", "success")
        else:
            companies_service.update(current_user, company, payload)
            flash("تم تحديث بيانات الشركة.", "success")
        return redirect(url_for("employer.company"))

    return render_template(
        "pages/employer_company.html",
        company=company,
        cities=CITIES,
        industries=INDUSTRIES,
        sizes=COMPANY_SIZES,
    )


@bp.post("/company/verification")
@login_required
def request_verification():
    company = _current_company()
    if company is None:
        flash("أنشئ ملف الشركة أولًا.", "error")
        return redirect(url_for("employer.company"))
    companies_service.request_verification(current_user, company, request.form.get("note"))
    flash("تم إرسال طلب التوثيق. عادةً تُراجع خلال يوم عمل.", "success")
    return redirect(url_for("employer.company"))


@bp.get("/jobs")
@login_required
def jobs():
    company = _current_company()
    if company is None:
        return redirect(url_for("employer.company"))
    rows = list(
        db.session.scalars(
            db.select(Job).where(Job.company_id == company.id).order_by(Job.created_at.desc())
        )
    )
    return render_template(
        "pages/employer_jobs.html", jobs=rows, company=company, status_labels=JOB_STATUS_LABELS
    )


@bp.route("/jobs/new", methods=["GET", "POST"])
@login_required
def job_new():
    company = _current_company()
    if company is None:
        flash("أنشئ ملف الشركة أولًا.", "error")
        return redirect(url_for("employer.company"))

    if request.method == "POST":
        job = jobs_service.create(current_user, company=company, data=request.form)
        if job.status == JobStatus.DRAFT.value:
            flash("تم حفظ الوظيفة كمسودة — ستُنشر بعد توثيق الشركة.", "info")
        else:
            flash("تم نشر الوظيفة بنجاح.", "success")
        return redirect(url_for("employer.jobs"))

    return render_template(
        "pages/employer_job_form.html",
        job=None,
        company=company,
        cities=CITIES,
        job_types=JOB_TYPE_LABELS,
        work_modes=WORK_MODE_LABELS,
        levels=CAREER_LEVEL_LABELS,
    )


@bp.route("/jobs/<job_id>/edit", methods=["GET", "POST"])
@login_required
def job_edit(job_id: str):
    job = jobs_service.get_for_owner(job_id, current_user)
    if request.method == "POST":
        jobs_service.update(current_user, job, request.form)
        flash("تم تحديث الوظيفة.", "success")
        return redirect(url_for("employer.jobs"))
    return render_template(
        "pages/employer_job_form.html",
        job=job,
        company=job.company,
        cities=CITIES,
        job_types=JOB_TYPE_LABELS,
        work_modes=WORK_MODE_LABELS,
        levels=CAREER_LEVEL_LABELS,
    )


@bp.post("/jobs/<job_id>/publish")
@login_required
def job_publish(job_id: str):
    job = jobs_service.get_for_owner(job_id, current_user)
    jobs_service.publish(current_user, job)
    flash("تم نشر الوظيفة.", "success")
    return redirect(url_for("employer.jobs"))


@bp.post("/jobs/<job_id>/close")
@login_required
def job_close(job_id: str):
    job = jobs_service.get_for_owner(job_id, current_user)
    jobs_service.close(current_user, job)
    flash("تم إغلاق الوظيفة.", "info")
    return redirect(url_for("employer.jobs"))


@bp.post("/jobs/<job_id>/delete")
@login_required
def job_delete(job_id: str):
    job = jobs_service.get_for_owner(job_id, current_user)
    jobs_service.delete(current_user, job)
    flash("تم حذف الوظيفة.", "info")
    return redirect(url_for("employer.jobs"))


@bp.get("/applicants")
@login_required
def applicants():
    company = _current_company()
    if company is None:
        return redirect(url_for("employer.company"))
    status = request.args.get("status") or None
    rows = applications_service.list_for_company(current_user, company.id, status)
    counts = {key: 0 for key in APPLICATION_STATUS_LABELS}
    for row in applications_service.list_for_company(current_user, company.id):
        counts[row.status] = counts.get(row.status, 0) + 1
    return render_template(
        "pages/employer_applicants.html",
        applications=rows,
        company=company,
        counts=counts,
        active_status=status,
        status_labels=APPLICATION_STATUS_LABELS,
    )


@bp.post("/applications/<application_id>/status")
@login_required
def application_status(application_id: str):
    try:
        applications_service.update_status(
            current_user,
            application_id,
            request.form.get("status", ""),
            request.form.get("note"),
        )
        flash("تم تحديث حالة الطلب وإشعار المتقدم.", "success")
    except DomainError as exc:
        flash(exc.message, "error")
    return redirect(request.referrer or url_for("employer.applicants"))
