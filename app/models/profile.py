"""Professional profile, education, experience, skills and privacy.

The profile is the centre of the platform: every row here belongs to exactly
one user and is edited only through the services layer, which re-checks
ownership before writing.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, UniqueConstraint

from app.extensions import db
from app.models.base import TimestampMixin, fk_column, pk_column


class Profile(TimestampMixin, db.Model):
    __tablename__ = "profiles"

    id = pk_column()
    user_id = fk_column("users", nullable=False, ondelete="CASCADE")

    # ── identity / presentation ─────────────────────────
    headline = db.Column(db.String(160))
    bio = db.Column(db.Text)
    city = db.Column(db.String(80), index=True)
    country = db.Column(db.String(80), default="العراق")
    address = db.Column(db.String(160))
    experience_years = db.Column(db.Integer, default=0)

    # Uploaded files live outside the web root and are served by /media/*.
    avatar_path = db.Column(db.String(255))
    cover_path = db.Column(db.String(255))

    # Kept for backwards compatibility with v2.0 rows; the normalised rows
    # below are the source of truth for the profile editor.
    skills = db.Column(db.JSON, default=list)
    education = db.Column(db.JSON, default=list)
    languages = db.Column(db.JSON, default=list)

    # ── links ───────────────────────────────────────────
    github_url = db.Column(db.String(255))
    linkedin_url = db.Column(db.String(255))
    portfolio_url = db.Column(db.String(255))
    website_url = db.Column(db.String(255))
    twitter_url = db.Column(db.String(255))
    facebook_url = db.Column(db.String(255))

    # ── CV ──────────────────────────────────────────────
    cv_path = db.Column(db.String(255))
    cv_url = db.Column(db.String(512))
    cv_filename = db.Column(db.String(255))
    cv_uploaded_at = db.Column(db.DateTime(timezone=True))

    is_open_to_work = db.Column(db.Boolean, nullable=False, default=True)
    open_to_relocate = db.Column(db.Boolean, nullable=False, default=False)

    # ── relationships ───────────────────────────────────
    user = db.relationship("User", back_populates="profile")
    educations = db.relationship(
        "Education",
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="Education.sort_order, Education.start_year.desc()",
    )
    experiences = db.relationship(
        "WorkExperience",
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="WorkExperience.sort_order, WorkExperience.start_date.desc()",
    )
    skills_list = db.relationship(
        "Skill",
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="Skill.sort_order, Skill.name",
    )
    languages_list = db.relationship(
        "Language",
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="Language.sort_order, Language.name",
    )
    certifications = db.relationship(
        "Certification",
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="Certification.sort_order, Certification.issue_date.desc()",
    )
    projects = db.relationship(
        "PortfolioProject",
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="PortfolioProject.sort_order, PortfolioProject.created_at.desc()",
    )

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_profiles_user"),
        CheckConstraint(
            "experience_years IS NULL OR (experience_years >= 0 AND experience_years <= 60)",
            name="ck_profiles_experience",
        ),
    )

    # ── derived helpers ─────────────────────────────────
    @property
    def skill_names(self) -> list[str]:
        names = [row.name for row in self.skills_list if row.name]
        if not names:
            names = [str(item) for item in (self.skills or []) if str(item).strip()]
        return names

    @property
    def language_names(self) -> list[str]:
        names = [row.name for row in self.languages_list if row.name]
        if not names:
            names = [str(item) for item in (self.languages or []) if str(item).strip()]
        return names

    @property
    def has_uploaded_avatar(self) -> bool:
        return bool(self.avatar_path)

    @property
    def has_uploaded_cover(self) -> bool:
        return bool(self.cover_path)

    @property
    def has_cv(self) -> bool:
        return bool(self.cv_path or self.cv_url)

    @property
    def completeness(self) -> int:
        """0-100 profile strength, weighted towards what employers open first."""
        checks = [
            bool(self.user and self.user.full_name),
            bool(self.headline),
            bool(self.bio),
            bool(self.city),
            bool(self.skill_names),
            bool(self.experiences),
            bool(self.educations),
            bool(self.user and self.user.phone),
            bool(self.has_cv),
            bool(self.avatar_path or (self.user and self.user.avatar_url)),
            bool(self.linkedin_url or self.portfolio_url or self.github_url),
        ]
        return round(100 * sum(1 for item in checks if item) / len(checks))

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Profile {self.user_id}>"


class Education(TimestampMixin, db.Model):
    __tablename__ = "profile_education"

    id = pk_column()
    profile_id = fk_column("profiles", nullable=False, ondelete="CASCADE")

    institution = db.Column(db.String(180), nullable=False)
    degree = db.Column(db.String(160))
    field_of_study = db.Column(db.String(160))
    start_year = db.Column(db.Integer)
    end_year = db.Column(db.Integer)
    grade = db.Column(db.String(80))
    description = db.Column(db.Text)
    is_current = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    profile = db.relationship("Profile", back_populates="educations")

    @property
    def period_label(self) -> str:
        start = str(self.start_year) if self.start_year else ""
        end = "الآن" if self.is_current else (str(self.end_year) if self.end_year else "")
        return " – ".join(part for part in (start, end) if part) or "—"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Education {self.institution}>"


class WorkExperience(TimestampMixin, db.Model):
    __tablename__ = "profile_experience"

    id = pk_column()
    profile_id = fk_column("profiles", nullable=False, ondelete="CASCADE")

    title = db.Column(db.String(180), nullable=False)
    company_name = db.Column(db.String(180), nullable=False)
    employment_type = db.Column(db.String(30))
    location = db.Column(db.String(120))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    is_current = db.Column(db.Boolean, nullable=False, default=False)
    description = db.Column(db.Text)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    profile = db.relationship("Profile", back_populates="experiences")

    @property
    def period_label(self) -> str:
        start = self.start_date.strftime("%m/%Y") if self.start_date else ""
        end = (
            "الآن"
            if self.is_current
            else (self.end_date.strftime("%m/%Y") if self.end_date else "")
        )
        return " – ".join(part for part in (start, end) if part) or "—"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<WorkExperience {self.title}>"


class Skill(TimestampMixin, db.Model):
    __tablename__ = "profile_skills"

    id = pk_column()
    profile_id = fk_column("profiles", nullable=False, ondelete="CASCADE")

    name = db.Column(db.String(100), nullable=False)
    level = db.Column(db.String(20), nullable=False, default="intermediate")
    years = db.Column(db.Integer)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    profile = db.relationship("Profile", back_populates="skills_list")

    __table_args__ = (
        UniqueConstraint("profile_id", "name", name="uq_profile_skill"),
        CheckConstraint(
            "level IN ('beginner','intermediate','advanced','expert')",
            name="ck_profile_skill_level",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Skill {self.name}>"


class Language(TimestampMixin, db.Model):
    __tablename__ = "profile_languages"

    id = pk_column()
    profile_id = fk_column("profiles", nullable=False, ondelete="CASCADE")

    name = db.Column(db.String(80), nullable=False)
    proficiency = db.Column(db.String(30), nullable=False, default="professional")
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    profile = db.relationship("Profile", back_populates="languages_list")

    __table_args__ = (
        UniqueConstraint("profile_id", "name", name="uq_profile_language"),
        CheckConstraint(
            "proficiency IN ('basic','conversational','professional','native','fluent')",
            name="ck_profile_language_proficiency",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Language {self.name}>"


class Certification(TimestampMixin, db.Model):
    __tablename__ = "profile_certifications"

    id = pk_column()
    profile_id = fk_column("profiles", nullable=False, ondelete="CASCADE")

    name = db.Column(db.String(180), nullable=False)
    issuer = db.Column(db.String(180))
    issue_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    credential_id = db.Column(db.String(160))
    credential_url = db.Column(db.String(512))
    description = db.Column(db.Text)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    profile = db.relationship("Profile", back_populates="certifications")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Certification {self.name}>"


class PortfolioProject(TimestampMixin, db.Model):
    __tablename__ = "profile_projects"

    id = pk_column()
    profile_id = fk_column("profiles", nullable=False, ondelete="CASCADE")

    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text)
    project_url = db.Column(db.String(512))
    repo_url = db.Column(db.String(512))
    image_url = db.Column(db.String(512))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    technologies = db.Column(db.JSON, default=list)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    profile = db.relationship("Profile", back_populates="projects")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PortfolioProject {self.title}>"


class UserPrivacySettings(TimestampMixin, db.Model):
    """Per-user visibility switches used by the public profile view."""

    __tablename__ = "user_privacy_settings"

    id = pk_column()
    user_id = fk_column("users", nullable=False, ondelete="CASCADE")

    profile_visibility = db.Column(
        db.String(20), nullable=False, default="public"
    )  # public | employers | private
    show_email = db.Column(db.Boolean, nullable=False, default=False)
    show_phone = db.Column(db.Boolean, nullable=False, default=False)
    show_location = db.Column(db.Boolean, nullable=False, default=True)
    show_education = db.Column(db.Boolean, nullable=False, default=True)
    show_experience = db.Column(db.Boolean, nullable=False, default=True)
    show_skills = db.Column(db.Boolean, nullable=False, default=True)
    show_languages = db.Column(db.Boolean, nullable=False, default=True)
    show_certifications = db.Column(db.Boolean, nullable=False, default=True)
    show_projects = db.Column(db.Boolean, nullable=False, default=True)
    show_cv = db.Column(db.Boolean, nullable=False, default=True)
    allow_messages = db.Column(db.Boolean, nullable=False, default=True)
    show_activity = db.Column(db.Boolean, nullable=False, default=True)

    user = db.relationship("User", back_populates="privacy")

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_privacy_user"),
        CheckConstraint(
            "profile_visibility IN ('public','employers','private')",
            name="ck_privacy_visibility",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UserPrivacySettings {self.user_id}>"


class AuthIdentity(TimestampMixin, db.Model):
    """External identities (currently Google) attached to a Mehna user."""

    __tablename__ = "auth_identities"

    id = pk_column()
    user_id = fk_column("users", nullable=False, ondelete="CASCADE")
    provider = db.Column(db.String(30), nullable=False, default="google")
    subject = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255))
    avatar_url = db.Column(db.String(512))
    last_login_at = db.Column(db.DateTime(timezone=True))

    user = db.relationship("User", back_populates="auth_identities")

    __table_args__ = (
        UniqueConstraint("provider", "subject", name="uq_auth_identity_subject"),
        db.Index("ix_auth_identity_user", "user_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuthIdentity {self.provider}:{self.subject}>"


class MessageThread(TimestampMixin, db.Model):
    __tablename__ = "message_threads"

    id = pk_column()
    # Keep the pair ordered (smaller UUID first) so a unique constraint can
    # prevent duplicate conversations regardless of who starts the chat.
    user_a_id = fk_column("users", nullable=False, ondelete="CASCADE")
    user_b_id = fk_column("users", nullable=False, ondelete="CASCADE")

    last_message_at = db.Column(db.DateTime(timezone=True))

    user_a = db.relationship("User", foreign_keys=[user_a_id])
    user_b = db.relationship("User", foreign_keys=[user_b_id])
    messages = db.relationship(
        "Message",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    __table_args__ = (
        UniqueConstraint("user_a_id", "user_b_id", name="uq_message_thread_pair"),
        db.Index("ix_message_thread_last", "last_message_at"),
    )

    def other_user(self, user_id: str):
        return self.user_b if self.user_a_id == user_id else self.user_a

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MessageThread {self.user_a_id}/{self.user_b_id}>"


class Message(TimestampMixin, db.Model):
    __tablename__ = "messages"

    id = pk_column()
    thread_id = fk_column("message_threads", nullable=False, ondelete="CASCADE")
    sender_id = fk_column("users", nullable=False, ondelete="CASCADE")
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)

    thread = db.relationship("MessageThread", back_populates="messages")
    sender = db.relationship("User")

    __table_args__ = (db.Index("ix_messages_thread_created", "thread_id", "created_at"),)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Message {self.id}>"
