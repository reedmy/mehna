"""Job search, publishing, and lifecycle."""

from __future__ import annotations

import contextlib
from datetime import timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Application, Company, Job, User
from app.models.base import utcnow
from app.models.enums import JobStatus, VerificationStatus
from app.services import plans_service
from app.services.errors import LimitReached, NotFound, PermissionDenied, ValidationError
from app.utils.arabic import normalize_ar, search_groups, slugify
from app.utils.security import sanitize_html, strip_tags

SORT_OPTIONS = {
    "newest": "الأحدث",
    "salary": "الأعلى راتبًا",
    "relevant": "الأكثر صلة",
}


def _public_query():
    return (
        db.select(Job)
        .join(Company)
        .options(joinedload(Job.company))
        .where(Job.status == JobStatus.PUBLISHED.value)
        .where(or_(Job.expires_at.is_(None), Job.expires_at > utcnow()))
    )


def search(filters: dict | None = None, *, page: int = 1, per_page: int = 12):
    filters = filters or {}
    stmt = _public_query()

    for group in search_groups(filters.get("q")):
        stmt = stmt.where(or_(*[Job.search_blob.contains(term) for term in group]))

    if city := filters.get("city"):
        stmt = stmt.where(Job.city == city)
    if job_type := filters.get("job_type"):
        stmt = stmt.where(Job.job_type == job_type)
    if work_mode := filters.get("work_mode"):
        stmt = stmt.where(Job.work_mode == work_mode)
    if industry := filters.get("industry"):
        stmt = stmt.where(Company.industry == industry)
    if level := filters.get("career_level"):
        stmt = stmt.where(Job.career_level == level)
    if filters.get("salary_min"):
        with contextlib.suppress(TypeError, ValueError):
            stmt = stmt.where(Job.salary_max >= int(filters["salary_min"]))
    if filters.get("verified_only"):
        stmt = stmt.where(Company.verification_status == VerificationStatus.VERIFIED.value)

    sort = filters.get("sort", "newest")
    if sort == "salary":
        stmt = stmt.order_by(Job.salary_max.desc().nullslast(), Job.published_at.desc())
    else:
        stmt = stmt.order_by(Job.is_featured.desc(), Job.published_at.desc())

    return db.paginate(stmt, page=max(1, page), per_page=per_page, error_out=False)


def get_public(job_id: str) -> Job | None:
    return db.session.scalar(_public_query().where(Job.id == job_id))


def get_for_owner(job_id: str, actor: User) -> Job:
    job = db.session.scalar(db.select(Job).options(joinedload(Job.company)).filter_by(id=job_id))
    if job is None:
        raise NotFound("الوظيفة غير موجودة.")
    if not actor.is_admin and job.company.owner_id != actor.id:
        raise PermissionDenied()
    return job


def create(actor: User, *, company: Company, data: dict) -> Job:
    if not actor.is_admin and company.owner_id != actor.id:
        raise PermissionDenied("لا تملك هذه الشركة.")

    allowed, message = plans_service.can_publish(company)
    if not allowed:
        raise LimitReached(message)

    title = strip_tags(data.get("title"))[:180]
    description = sanitize_html(data.get("description"))
    if len(title) < 4:
        raise ValidationError("عنوان الوظيفة قصير جدًا.")
    if len(strip_tags(description)) < 30:
        raise ValidationError("أضف وصفًا للوظيفة (30 حرفًا على الأقل).")

    salary_min = _to_int(data.get("salary_min"))
    salary_max = _to_int(data.get("salary_max"))
    if salary_min and salary_max and salary_min > salary_max:
        raise ValidationError("الحد الأدنى للراتب أكبر من الحد الأعلى.")

    verified = company.verification_status == VerificationStatus.VERIFIED.value
    job = Job(
        company_id=company.id,
        posted_by_id=actor.id,
        title=title,
        slug="",
        description=description,
        requirements=_as_list(data.get("requirements")),
        benefits=_as_list(data.get("benefits")),
        city=data.get("city") or None,
        job_type=data.get("job_type") or "full_time",
        work_mode=data.get("work_mode") or "onsite",
        career_level=data.get("career_level") or None,
        experience_years_min=_to_int(data.get("experience_years_min")) or 0,
        salary_min=salary_min,
        salary_max=salary_max,
        currency=data.get("currency") or "IQD",
        salary_negotiable=bool(data.get("salary_negotiable")),
        status=JobStatus.PUBLISHED.value if verified else JobStatus.DRAFT.value,
        published_at=utcnow() if verified else None,
        expires_at=utcnow() + timedelta(days=45),
    )
    db.session.add(job)
    db.session.flush()
    job.slug = f"{slugify(title)}-{job.id[:8]}"
    job.refresh_search_fields()
    db.session.commit()
    return job


def update(actor: User, job: Job, data: dict) -> Job:
    if not actor.is_admin and job.company.owner_id != actor.id:
        raise PermissionDenied()

    title = strip_tags(data.get("title"))[:180]
    if len(title) < 4:
        raise ValidationError("عنوان الوظيفة قصير جدًا.")
    description = sanitize_html(data.get("description"))
    if len(strip_tags(description)) < 30:
        raise ValidationError("أضف وصفًا للوظيفة (30 حرفًا على الأقل).")

    salary_min = _to_int(data.get("salary_min"))
    salary_max = _to_int(data.get("salary_max"))
    if salary_min and salary_max and salary_min > salary_max:
        raise ValidationError("الحد الأدنى للراتب أكبر من الحد الأعلى.")

    job.title = title
    job.description = description
    job.requirements = _as_list(data.get("requirements"))
    job.benefits = _as_list(data.get("benefits"))
    job.city = data.get("city") or None
    job.job_type = data.get("job_type") or job.job_type
    job.work_mode = data.get("work_mode") or job.work_mode
    job.career_level = data.get("career_level") or None
    job.experience_years_min = _to_int(data.get("experience_years_min")) or 0
    job.salary_min = salary_min
    job.salary_max = salary_max
    job.currency = data.get("currency") or "IQD"
    job.salary_negotiable = bool(data.get("salary_negotiable"))
    job.refresh_search_fields()
    db.session.commit()
    return job


def publish(actor: User, job: Job) -> Job:
    if not actor.is_admin and job.company.owner_id != actor.id:
        raise PermissionDenied()
    if job.company.verification_status != VerificationStatus.VERIFIED.value:
        raise PermissionDenied("لا يمكن نشر الوظيفة قبل توثيق الشركة.")
    job.status = JobStatus.PUBLISHED.value
    job.published_at = job.published_at or utcnow()
    job.expires_at = utcnow() + timedelta(days=45)
    db.session.commit()
    return job


def close(actor: User, job: Job) -> Job:
    if not actor.is_admin and job.company.owner_id != actor.id:
        raise PermissionDenied()
    job.status = JobStatus.CLOSED.value
    db.session.commit()
    return job


def delete(actor: User, job: Job) -> None:
    if not actor.is_admin and job.company.owner_id != actor.id:
        raise PermissionDenied()
    db.session.delete(job)
    db.session.commit()


def increment_views(job: Job) -> None:
    job.views_count = (job.views_count or 0) + 1
    db.session.commit()


def expire_stale() -> int:
    result = db.session.execute(
        db.update(Job)
        .where(Job.status == JobStatus.PUBLISHED.value)
        .where(Job.expires_at.is_not(None))
        .where(Job.expires_at < utcnow())
        .values(status=JobStatus.EXPIRED.value)
    )
    db.session.commit()
    return result.rowcount or 0


def employer_stats(company: Company) -> dict:
    active = db.session.scalar(
        db.select(func.count(Job.id))
        .where(Job.company_id == company.id)
        .where(Job.status == JobStatus.PUBLISHED.value)
    )
    total_apps = db.session.scalar(
        db.select(func.count(Application.id))
        .join(Job, Application.job_id == Job.id)
        .where(Job.company_id == company.id)
    )
    new_apps = db.session.scalar(
        db.select(func.count(Application.id))
        .join(Job, Application.job_id == Job.id)
        .where(Job.company_id == company.id)
        .where(Application.status == "submitted")
    )
    return {
        "active_jobs": active or 0,
        "total_applications": total_apps or 0,
        "new_applications": new_apps or 0,
    }


# ── homepage / discovery ─────────────────────────────────


def recommended_for(user: User, *, limit: int = 6) -> list[Job]:
    """Real recommendations from the user's city and saved profile skills."""
    if user is None or not user.is_authenticated:
        return list(db.session.scalars(_public_query().limit(limit)))

    applied = db.session.scalars(
        db.select(Application.job_id).where(Application.seeker_id == user.id)
    )
    applied_ids = [row for row in applied]
    stmt = _public_query()
    if applied_ids:
        stmt = stmt.where(Job.id.not_in(applied_ids))

    profile = user.profile
    conditions = []
    if profile and profile.city:
        conditions.append(Job.city == profile.city)
    for skill in (profile.skill_names[:6] if profile else []):
        term = normalize_ar(skill)
        if term:
            conditions.append(Job.search_blob.contains(term))
    if conditions:
        stmt = stmt.where(or_(*conditions))
    rows = list(
        db.session.scalars(
            stmt.order_by(Job.is_featured.desc(), Job.published_at.desc()).limit(limit)
        )
    )
    if len(rows) < limit:
        excluded = {job.id for job in rows}
        fallback = db.session.scalars(
            _public_query()
            .where(Job.id.not_in(excluded or [""]))
            .order_by(Job.published_at.desc())
            .limit(limit - len(rows))
        )
        rows.extend(fallback)
    return rows


def trending(limit: int = 5) -> list[Job]:
    return list(
        db.session.scalars(
            _public_query()
            .order_by(Job.is_featured.desc(), Job.applications_count.desc(), Job.views_count.desc())
            .limit(limit)
        )
    )


def recently_added(limit: int = 4) -> list[Job]:
    return list(db.session.scalars(_public_query().limit(limit)))


def popular_industries(limit: int = 6) -> list[tuple[str, int]]:
    return [
        (row[0], row[1])
        for row in db.session.execute(
            db.select(Company.industry, func.count(Job.id))
            .join(Job, Job.company_id == Company.id)
            .where(Job.status == JobStatus.PUBLISHED.value)
            .where(Company.industry.is_not(None))
            .group_by(Company.industry)
            .order_by(func.count(Job.id).desc())
            .limit(limit)
        )
    ]


def recommended_companies(*, limit: int = 4) -> list[tuple[Company, int]]:
    rows = db.session.execute(
        db.select(Company, func.count(Job.id))
        .join(Job, Job.company_id == Company.id)
        .where(Job.status == JobStatus.PUBLISHED.value)
        .where(Company.verification_status == VerificationStatus.VERIFIED.value)
        .group_by(Company.id)
        .order_by(func.count(Job.id).desc(), Company.name)
        .limit(limit)
    )
    return [(row[0], row[1]) for row in rows]


def home_stats() -> dict:
    return {
        "jobs": db.session.scalar(
            db.select(func.count(Job.id)).where(Job.status == JobStatus.PUBLISHED.value)
        )
        or 0,
        "companies": db.session.scalar(db.select(func.count(Company.id))) or 0,
        "seekers": db.session.scalar(db.select(func.count(User.id)).where(User.role == "seeker"))
        or 0,
        "employers": db.session.scalar(
            db.select(func.count(User.id)).where(User.role == "employer")
        )
        or 0,
        "applications": db.session.scalar(db.select(func.count(Application.id))) or 0,
    }


# ── helpers ──────────────────────────────────────────────


def _to_int(value) -> int | None:
    try:
        number = int(value)
        return number if number >= 0 else None
    except (TypeError, ValueError):
        return None


def _as_list(value) -> list[str]:
    if not value:
        return []
    items = value if isinstance(value, list) else str(value).replace("\r", "").split("\n")
    cleaned = [strip_tags(item).strip()[:200] for item in items]
    return [item for item in cleaned if item][:20]
