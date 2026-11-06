"""User accounts (profiles live in models/profile.py)."""

from __future__ import annotations

from flask_login import UserMixin
from sqlalchemy import CheckConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.base import TimestampMixin, pk_column, utcnow
from app.models.enums import Role


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = pk_column()
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), index=True)  # E.164, e.g. +9647701234567
    role = db.Column(db.String(20), nullable=False, default=Role.SEEKER.value, index=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    email_verified_at = db.Column(db.DateTime(timezone=True))
    phone_verified_at = db.Column(db.DateTime(timezone=True))
    last_login_at = db.Column(db.DateTime(timezone=True))

    # Google Sign-In (OAuth 2.0 / OpenID Connect)
    google_id = db.Column(db.String(64), unique=True, index=True)
    avatar_url = db.Column(db.String(512))

    plan = db.Column(db.String(20), nullable=False, default="free")
    plan_renews_at = db.Column(db.DateTime(timezone=True))

    profile = db.relationship(
        "Profile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    privacy = db.relationship(
        "UserPrivacySettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    auth_identities = db.relationship(
        "AuthIdentity", back_populates="user", cascade="all, delete-orphan"
    )
    companies = db.relationship(
        "Company",
        back_populates="owner",
        cascade="all, delete-orphan",
        foreign_keys="Company.owner_id",
    )
    applications = db.relationship(
        "Application", back_populates="seeker", cascade="all, delete-orphan"
    )
    notifications = db.relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )
    saved_jobs = db.relationship("SavedJob", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("role IN ('seeker','employer','admin')", name="ck_users_role"),
        CheckConstraint("plan IN ('free','pro','business')", name="ck_users_plan"),
    )

    # ── password helpers ────────────────────────────────
    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw, method="scrypt")

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    # ── Flask-Login ─────────────────────────────────────
    @property
    def is_active_user(self) -> bool:
        return bool(self.is_active)

    @property
    def is_employer(self) -> bool:
        return self.role in (Role.EMPLOYER.value, Role.ADMIN.value)

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN.value

    @property
    def first_name(self) -> str:
        return (self.full_name or "").split(" ")[0]

    @property
    def is_seeker(self) -> bool:
        return self.role == Role.SEEKER.value

    @property
    def display_avatar(self) -> str | None:
        """Uploaded avatar wins over the Google picture."""
        if self.profile and self.profile.avatar_path:
            return f"/media/avatar/{self.id}"
        return self.avatar_url

    @property
    def profile_completeness(self) -> int:
        return self.profile.completeness if self.profile else 0

    def touch_login(self) -> None:
        self.last_login_at = utcnow()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.email}>"
