"""Job postings."""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin, fk_column, pk_column
from app.models.enums import JobStatus, JobType


class Job(TimestampMixin, db.Model):
    __tablename__ = "jobs"

    id = pk_column()
    company_id = fk_column("companies", nullable=False, ondelete="CASCADE")
    posted_by_id = fk_column("users", nullable=False, ondelete="CASCADE")

    title = db.Column(db.String(180), nullable=False, index=True)
    slug = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    # Pre-normalised search fields (Arabic folding happens on write, not on read).
    title_norm = db.Column(db.String(200), index=True)
    search_blob = db.Column(db.Text)
    requirements = db.Column(db.JSON, default=list)
    benefits = db.Column(db.JSON, default=list)

    city = db.Column(db.String(80), index=True)
    job_type = db.Column(db.String(20), nullable=False, default=JobType.FULL_TIME.value, index=True)
    work_mode = db.Column(db.String(20), nullable=False, default="onsite", index=True)
    career_level = db.Column(db.String(20), index=True)
    experience_years_min = db.Column(db.Integer, default=0)

    salary_min = db.Column(db.Integer)
    salary_max = db.Column(db.Integer)
    currency = db.Column(db.String(8), default="IQD")
    salary_negotiable = db.Column(db.Boolean, nullable=False, default=True)

    status = db.Column(db.String(20), nullable=False, default=JobStatus.DRAFT.value, index=True)
    is_featured = db.Column(db.Boolean, nullable=False, default=False)
    views_count = db.Column(db.Integer, nullable=False, default=0)
    applications_count = db.Column(db.Integer, nullable=False, default=0)

    published_at = db.Column(db.DateTime(timezone=True), index=True)
    expires_at = db.Column(db.DateTime(timezone=True), index=True)

    company = db.relationship("Company", back_populates="jobs")
    posted_by = db.relationship("User", foreign_keys=[posted_by_id])
    applications = db.relationship(
        "Application", back_populates="job", cascade="all, delete-orphan"
    )

    # ── derived helpers used by templates ───────────────
    @property
    def is_open(self) -> bool:
        return self.status == JobStatus.PUBLISHED.value

    @property
    def salary_label(self) -> str:
        if self.salary_negotiable or (not self.salary_min and not self.salary_max):
            return "تفاوض"
        currency = self.currency or "IQD"
        if self.salary_min and self.salary_max:
            return f"{self.salary_min:,} – {self.salary_max:,} {currency}"
        value = self.salary_min or self.salary_max
        return f"{value:,} {currency}"

    @property
    def competition_label(self) -> str | None:
        if self.applications_count is None:
            return None
        if self.applications_count < 10:
            return "أقل من ١٠ متقدمين"
        return None

    def refresh_search_fields(self) -> None:
        from app.utils.arabic import normalize_ar, strip_markup

        company_name = self.company.name if self.company else ""
        self.title_norm = normalize_ar(self.title)
        self.search_blob = " ".join(
            filter(
                None,
                [
                    normalize_ar(self.title),
                    normalize_ar(company_name),
                    normalize_ar(self.city),
                    normalize_ar(strip_markup(self.description))[:4000],
                ],
            )
        )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Job {self.title}>"
