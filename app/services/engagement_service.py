"""Saved jobs and job reports."""

from __future__ import annotations

from app.extensions import db
from app.models import Job, JobReport, SavedJob, User
from app.models.enums import ReportStatus
from app.services.errors import ValidationError


def is_saved(user: User, job_id: str) -> bool:
    return (
        db.session.scalar(db.select(SavedJob).filter_by(user_id=user.id, job_id=job_id)) is not None
    )


def toggle_save(user: User, job: Job) -> bool:
    """Returns True when the job is now saved."""
    existing = db.session.scalar(db.select(SavedJob).filter_by(user_id=user.id, job_id=job.id))
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return False
    db.session.add(SavedJob(user_id=user.id, job_id=job.id))
    db.session.commit()
    return True


def list_saved(user: User) -> list[SavedJob]:
    return list(
        db.session.scalars(
            db.select(SavedJob)
            .where(SavedJob.user_id == user.id)
            .order_by(SavedJob.created_at.desc())
        )
    )


def report_job(user: User | None, job: Job, reason: str, details: str | None = None) -> JobReport:
    if not reason:
        raise ValidationError("اختر سبب الإبلاغ.")
    existing = None
    if user is not None:
        existing = db.session.scalar(
            db.select(JobReport).filter_by(job_id=job.id, reporter_id=user.id)
        )
    if existing:
        raise ValidationError("أبلغت عن هذه الوظيفة مسبقًا، شكرًا لك.")
    row = JobReport(
        job_id=job.id,
        reporter_id=user.id if user else None,
        reason=reason,
        details=(details or "").strip()[:1000] or None,
        status=ReportStatus.OPEN.value,
    )
    db.session.add(row)
    db.session.commit()
    return row
