"""Applications: apply, withdraw, review, and status transitions."""

from __future__ import annotations

from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Application, Job, Profile, User
from app.models.base import utcnow
from app.models.enums import (
    APPLICATION_STATUS_LABELS,
    ApplicationStatus,
    NotificationType,
)
from app.services import notifications_service
from app.services.errors import NotFound, PermissionDenied, ValidationError

VALID_TRANSITIONS = {
    ApplicationStatus.SUBMITTED.value: {
        ApplicationStatus.VIEWED.value,
        ApplicationStatus.SHORTLISTED.value,
        ApplicationStatus.REJECTED.value,
    },
    ApplicationStatus.VIEWED.value: {
        ApplicationStatus.SHORTLISTED.value,
        ApplicationStatus.REJECTED.value,
    },
    ApplicationStatus.SHORTLISTED.value: {
        ApplicationStatus.INTERVIEW.value,
        ApplicationStatus.REJECTED.value,
    },
    ApplicationStatus.INTERVIEW.value: {
        ApplicationStatus.ACCEPTED.value,
        ApplicationStatus.REJECTED.value,
    },
}


def apply(seeker: User, job: Job, cover_letter: str | None = None) -> Application:
    if not job.is_open:
        raise ValidationError("هذه الوظيفة لم تعد متاحة للتقديم.")
    if job.company.owner_id == seeker.id:
        raise ValidationError("لا يمكنك التقديم على وظيفة نشرتها شركتك.")
    existing = db.session.scalar(
        db.select(Application).filter_by(job_id=job.id, seeker_id=seeker.id)
    )
    if existing:
        raise ValidationError("قدّمت على هذه الوظيفة مسبقًا.")

    app_row = Application(
        job_id=job.id,
        seeker_id=seeker.id,
        cover_letter=(cover_letter or "").strip()[:4000] or None,
        status=ApplicationStatus.SUBMITTED.value,
        status_updated_at=utcnow(),
    )
    job.applications_count = (job.applications_count or 0) + 1
    db.session.add(app_row)
    notifications_service.notify(
        job.company.owner,
        type=NotificationType.APPLICATION_NEW.value,
        title=f"متقدم جديد على «{job.title}»",
        body=f"{seeker.full_name} قدّم على وظيفتك.",
        link="/employer/applicants",
        commit=False,
    )
    db.session.commit()
    return app_row


def withdraw(seeker: User, application_id: str) -> Application:
    app_row = db.session.get(Application, application_id)
    if app_row is None:
        raise NotFound("الطلب غير موجود.")
    if app_row.seeker_id != seeker.id:
        raise PermissionDenied()
    if app_row.status in (ApplicationStatus.ACCEPTED.value,):
        raise ValidationError("لا يمكن سحب طلب تم قبوله.")
    app_row.status = ApplicationStatus.WITHDRAWN.value
    app_row.status_updated_at = utcnow()
    db.session.commit()
    return app_row


def list_for_job(actor: User, job: Job, status: str | None = None) -> list[Application]:
    if not actor.is_admin and job.company.owner_id != actor.id:
        raise PermissionDenied()
    stmt = (
        db.select(Application)
        .options(joinedload(Application.seeker).joinedload(User.profile))
        .where(Application.job_id == job.id)
        .order_by(Application.created_at.desc())
    )
    if status:
        stmt = stmt.where(Application.status == status)
    return list(db.session.scalars(stmt))


def list_for_company(actor: User, company_id: str, status: str | None = None) -> list[Application]:
    stmt = (
        db.select(Application)
        .join(Job, Application.job_id == Job.id)
        .options(
            joinedload(Application.seeker).joinedload(User.profile),
            joinedload(Application.job).joinedload(Job.company),
        )
        .where(Job.company_id == company_id)
        .order_by(Application.created_at.desc())
    )
    if status:
        stmt = stmt.where(Application.status == status)
    return list(db.session.scalars(stmt))


def list_for_seeker(seeker: User) -> list[Application]:
    return list(
        db.session.scalars(
            db.select(Application)
            .options(joinedload(Application.job).joinedload(Job.company))
            .where(Application.seeker_id == seeker.id)
            .order_by(Application.created_at.desc())
        )
    )


def update_status(
    actor: User, application_id: str, new_status: str, note: str | None = None
) -> Application:
    app_row = db.session.scalar(
        db.select(Application)
        .options(joinedload(Application.job).joinedload(Job.company))
        .filter_by(id=application_id)
    )
    if app_row is None:
        raise NotFound("الطلب غير موجود.")
    if not actor.is_admin and app_row.job.company.owner_id != actor.id:
        raise PermissionDenied()
    if new_status not in APPLICATION_STATUS_LABELS:
        raise ValidationError("حالة غير معروفة.")

    allowed = VALID_TRANSITIONS.get(app_row.status, set())
    if new_status not in allowed and not actor.is_admin:
        raise ValidationError("لا يمكن الانتقال إلى هذه الحالة من الحالة الحالية.")

    app_row.status = new_status
    app_row.status_updated_at = utcnow()
    if note:
        app_row.employer_note = note.strip()[:2000]

    notifications_service.notify(
        app_row.seeker,
        type=NotificationType.APPLICATION_STATUS.value,
        title=f"تحديث على طلبك: {APPLICATION_STATUS_LABELS[new_status]}",
        body=f"وظيفة «{app_row.job.title}» — {app_row.job.company.name}",
        link="/dashboard/applications",
        commit=False,
    )
    db.session.commit()
    return app_row


def profile_of(application: Application) -> Profile | None:
    return application.seeker.profile if application.seeker else None
