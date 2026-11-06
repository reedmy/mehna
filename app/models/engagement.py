"""Engagement: saved jobs, saved searches, job reports."""

from __future__ import annotations

from sqlalchemy import UniqueConstraint

from app.extensions import db
from app.models.base import TimestampMixin, fk_column, pk_column
from app.models.enums import ReportStatus


class SavedJob(TimestampMixin, db.Model):
    __tablename__ = "saved_jobs"

    id = pk_column()
    user_id = fk_column("users", nullable=False)
    job_id = fk_column("jobs", nullable=False)

    user = db.relationship("User", back_populates="saved_jobs")
    job = db.relationship("Job")

    __table_args__ = (UniqueConstraint("user_id", "job_id", name="uq_saved_jobs"),)


class SavedSearch(TimestampMixin, db.Model):
    __tablename__ = "saved_searches"

    id = pk_column()
    user_id = fk_column("users", nullable=False)
    label = db.Column(db.String(120), nullable=False)
    query = db.Column(db.JSON, default=dict)  # {q, city, job_type, career_level, ...}
    channel = db.Column(db.String(20), nullable=False, default="email")  # email|whatsapp|telegram
    frequency = db.Column(db.String(20), nullable=False, default="daily")  # instant|daily|weekly
    last_sent_at = db.Column(db.DateTime(timezone=True))

    user = db.relationship("User")


class JobReport(TimestampMixin, db.Model):
    __tablename__ = "job_reports"

    id = pk_column()
    job_id = fk_column("jobs", nullable=False)
    reporter_id = fk_column("users", nullable=True, ondelete="SET NULL")
    reason = db.Column(db.String(40), nullable=False)
    details = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default=ReportStatus.OPEN.value, index=True)
    resolution_note = db.Column(db.Text)

    job = db.relationship("Job")
    reporter = db.relationship("User")

    __table_args__ = (db.Index("ix_job_reports_job_status", "job_id", "status"),)
