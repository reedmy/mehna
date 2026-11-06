"""Applications (seeker → job)."""

from __future__ import annotations

from sqlalchemy import UniqueConstraint

from app.extensions import db
from app.models.base import TimestampMixin, fk_column, pk_column, utcnow
from app.models.enums import ApplicationStatus


class Application(TimestampMixin, db.Model):
    __tablename__ = "applications"

    id = pk_column()
    job_id = fk_column("jobs", nullable=False, ondelete="CASCADE")
    seeker_id = fk_column("users", nullable=False, ondelete="CASCADE")

    cover_letter = db.Column(db.Text)
    status = db.Column(
        db.String(20), nullable=False, default=ApplicationStatus.SUBMITTED.value, index=True
    )
    employer_note = db.Column(db.Text)
    status_updated_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    job = db.relationship("Job", back_populates="applications")
    seeker = db.relationship("User", back_populates="applications")

    __table_args__ = (
        UniqueConstraint("job_id", "seeker_id", name="uq_applications_job_seeker"),
        db.Index("ix_applications_job_status", "job_id", "status"),
    )

    @property
    def is_active(self) -> bool:
        return self.status not in (
            ApplicationStatus.REJECTED.value,
            ApplicationStatus.WITHDRAWN.value,
        )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Application {self.id} {self.status}>"
