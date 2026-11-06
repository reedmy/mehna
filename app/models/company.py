"""Companies — now with an explicit owner (no more ownership-through-jobs)."""

from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin, fk_column, pk_column
from app.models.enums import VerificationStatus


class Company(TimestampMixin, db.Model):
    __tablename__ = "companies"

    id = pk_column()
    owner_id = fk_column("users", nullable=False, ondelete="CASCADE")
    name = db.Column(db.String(160), nullable=False, index=True)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    website = db.Column(db.String(255))
    city = db.Column(db.String(80), index=True)
    industry = db.Column(db.String(80), index=True)
    size = db.Column(db.String(20))
    logo_url = db.Column(db.String(255))

    verification_status = db.Column(
        db.String(20), nullable=False, default=VerificationStatus.UNVERIFIED.value, index=True
    )
    verification_note = db.Column(db.Text)
    verified_at = db.Column(db.DateTime(timezone=True))
    verified_by_id = fk_column("users", nullable=True, ondelete="SET NULL")

    owner = db.relationship("User", back_populates="companies", foreign_keys=[owner_id])
    verifier = db.relationship("User", foreign_keys=[verified_by_id])
    jobs = db.relationship("Job", back_populates="company", cascade="all, delete-orphan")

    @property
    def is_verified(self) -> bool:
        return self.verification_status == VerificationStatus.VERIFIED.value

    @property
    def initials(self) -> str:
        parts = [p for p in (self.name or "").split() if p]
        return "".join(p[0] for p in parts[:2]) if parts else "؟"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Company {self.name}>"
