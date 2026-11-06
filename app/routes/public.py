"""Public pages: home, job search, job detail, companies, static pages."""

from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Company, Job, SavedJob
from app.models.enums import (
    CAREER_LEVEL_LABELS,
    CITIES,
    INDUSTRIES,
    JOB_TYPE_LABELS,
    WORK_MODE_LABELS,
    JobStatus,
    VerificationStatus,
)
from app.services import (
    applications_service,
    auth_service,
    engagement_service,
    jobs_service,
    profiles_service,
)
from app.services.errors import ValidationError

bp = Blueprint("public", __name__)


@bp.get("/")
def home():
    profile = (
        profiles_service.get_or_create(current_user) if current_user.is_authenticated else None
    )
    saved_ids = set()
    if current_user.is_authenticated:
        saved_ids = set(
            db.session.scalars(
                db.select(SavedJob.job_id).where(SavedJob.user_id == current_user.id)
            )
        )

    pagination = jobs_service.search(
        {"city": profile.city if profile else None}, page=1, per_page=6
    )
    latest = pagination.items
    if not latest:
        latest = jobs_service.recently_added(6)

    cities = [
        row
        for row in db.session.execute(
            db.select(Job.city, func.count(Job.id))
            .where(Job.status == JobStatus.PUBLISHED.value)
            .where(Job.city.is_not(None))
            .group_by(Job.city)
            .order_by(func.count(Job.id).desc())
            .limit(8)
        )
    ]
    applications_count = 0
    if current_user.is_authenticated:
        from app.models import Application

        applications_count = (
            db.session.scalar(
                db.select(func.count(Application.id)).where(
                    Application.seeker_id == current_user.id
                )
            )
            or 0
        )
    return render_template(
        "pages/home.html",
        jobs=latest,
        stats=jobs_service.home_stats(),
        cities=cities,
        industries=INDUSTRIES,
        trending=jobs_service.trending(5),
        recommended_companies=jobs_service.recommended_companies(limit=4),
        popular_industries=jobs_service.popular_industries(6),
        recent=jobs_service.recently_added(4),
        profile=profile,
        saved_ids=saved_ids,
        applications_count=applications_count,
    )


@bp.get("/jobs")
def jobs():
    filters = {
        "q": request.args.get("q", "").strip(),
        "city": request.args.get("city") or None,
        "industry": request.args.get("industry") or None,
        "job_type": request.args.get("job_type") or None,
        "work_mode": request.args.get("work_mode") or None,
        "career_level": request.args.get("career_level") or None,
        "salary_min": request.args.get("salary_min") or None,
        "verified_only": request.args.get("verified_only") == "1",
        "sort": request.args.get("sort", "newest"),
    }
    page = request.args.get("page", 1, type=int)
    pagination = jobs_service.search(filters, page=page, per_page=12)
    saved_ids = set()
    if current_user.is_authenticated:
        saved_ids = set(
            db.session.scalars(
                db.select(SavedJob.job_id).where(SavedJob.user_id == current_user.id)
            )
        )

    context = {
        "pagination": pagination,
        "filters": filters,
        "cities": CITIES,
        "industries": INDUSTRIES,
        "job_types": JOB_TYPE_LABELS,
        "work_modes": WORK_MODE_LABELS,
        "levels": CAREER_LEVEL_LABELS,
        "total": pagination.total,
        "saved_ids": saved_ids,
    }
    if request.headers.get("HX-Request"):
        return render_template("pages/_job_results.html", **context)
    return render_template("pages/jobs.html", **context)


@bp.get("/jobs/<job_id>/<slug>")
def job_detail(job_id: str, slug: str):
    job = jobs_service.get_public(job_id)
    if job is None:
        abort(404)

    viewed = session.get("viewed_jobs", [])
    if job_id not in viewed:
        jobs_service.increment_views(job)
        session["viewed_jobs"] = (viewed + [job_id])[-30:]

    saved = False
    applied = False
    from flask_login import current_user

    if current_user.is_authenticated:
        saved = engagement_service.is_saved(current_user, job.id)
        from app.models import Application

        applied = (
            db.session.scalar(
                db.select(Application).filter_by(job_id=job.id, seeker_id=current_user.id)
            )
            is not None
        )

    similar = list(
        db.session.scalars(
            jobs_service._public_query()
            .where(Job.id != job.id)
            .where(Job.city == job.city if job.city else Job.id.is_not(None))
            .limit(3)
        )
    )
    return render_template(
        "pages/job_detail.html", job=job, saved=saved, applied=applied, similar=similar
    )


@bp.post("/jobs/<job_id>/apply")
def apply(job_id: str):
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.path))
    if current_user.role != "seeker":
        flash("التقديم متاح لحسابات الباحثين عن عمل فقط.", "error")
        return redirect(
            url_for("public.job_detail", job_id=job_id, slug=request.form.get("slug", "job"))
        )

    job = jobs_service.get_public(job_id)
    if job is None:
        abort(404)

    # Progressive profiling: only ask for contact details when they are missing.
    if not current_user.phone:
        flash("نحتاج رقم هاتفك مرة واحدة فقط — احفظه وسنستخدمه في طلباتك القادمة.", "info")
        return redirect(url_for("public.apply_form", job_id=job.id, slug=job.slug))

    try:
        applications_service.apply(current_user, job, request.form.get("cover_letter"))
    except ValidationError as exc:
        flash(exc.message, "error")
        return redirect(url_for("public.job_detail", job_id=job.id, slug=job.slug))

    flash("تم إرسال طلبك. ستصلك إشعارات عند تغيّر الحالة.", "success")
    return redirect(url_for("seeker.applications"))


@bp.route("/jobs/<job_id>/<slug>/apply", methods=["GET", "POST"])
@login_required
def apply_form(job_id: str, slug: str):
    """One-time contact details + cover letter, then apply. Values are reused later."""
    if current_user.role != "seeker":
        flash("التقديم متاح لحسابات الباحثين عن عمل فقط.", "error")
        return redirect(url_for("public.job_detail", job_id=job_id, slug=slug))

    job = jobs_service.get_public(job_id)
    if job is None:
        abort(404)

    from app.models import Application

    existing = db.session.scalar(
        db.select(Application).filter_by(job_id=job.id, seeker_id=current_user.id)
    )
    if existing is not None:
        flash("قدّمت على هذه الوظيفة مسبقًا.", "info")
        return redirect(url_for("seeker.applications"))

    profile = profiles_service.get_or_create(current_user)
    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        city = request.form.get("city") or ""
        cv_url = (request.form.get("cv_url") or "").strip()[:512]
        cover_letter = request.form.get("cover_letter")
        save_to_profile = request.form.get("save_to_profile") == "1"

        try:
            if not phone:
                raise ValidationError("أدخل رقم هاتفك ليتمكن صاحب العمل من التواصل معك.")
            if cv_url and not (cv_url.startswith("http://") or cv_url.startswith("https://")):
                raise ValidationError("رابط السيرة الذاتية يجب أن يبدأ بـ https://")

            # Name + phone live on the account: always keep them.
            auth_service.update_identity(current_user, full_name=full_name, phone=phone)

            if save_to_profile:
                if city in CITIES:
                    profile.city = city
                profile.cv_url = cv_url or profile.cv_url

            applications_service.apply(current_user, job, cover_letter)
        except ValidationError as exc:
            db.session.rollback()
            flash(exc.message, "error")
            return (
                render_template(
                    "pages/apply.html",
                    job=job,
                    profile=profile,
                    cities=CITIES,
                    form=request.form,
                ),
                422,
            )

        flash("تم إرسال طلبك. ستصلك إشعارات عند تغيّر الحالة.", "success")
        return redirect(url_for("seeker.applications"))

    return render_template(
        "pages/apply.html",
        job=job,
        profile=profile,
        cities=CITIES,
        form={
            "full_name": current_user.full_name,
            "phone": current_user.phone or "",
            "city": profile.city or "",
            "cv_url": profile.cv_url or "",
        },
    )


@bp.get("/companies")
def companies():
    page = request.args.get("page", 1, type=int)
    stmt = (
        db.select(Company)
        .where(Company.verification_status == VerificationStatus.VERIFIED.value)
        .order_by(Company.name.asc())
    )
    pagination = db.paginate(stmt, page=page, per_page=12, error_out=False)
    return render_template("pages/companies.html", pagination=pagination)


@bp.get("/companies/<slug>")
def company_detail(slug: str):
    company = db.session.scalar(
        db.select(Company).options(joinedload(Company.jobs)).filter_by(slug=slug)
    )
    if company is None:
        abort(404)
    open_jobs = [j for j in company.jobs if j.is_open]
    return render_template("pages/company_detail.html", company=company, jobs=open_jobs)


@bp.get("/pricing")
def pricing():
    from flask import current_app

    return render_template("pages/pricing.html", plans=current_app.config["PLAN_LIMITS"])


@bp.get("/about")
def about():
    return render_template("pages/about.html")


@bp.get("/how-it-works")
def how_it_works():
    return render_template("pages/how_it_works.html")
