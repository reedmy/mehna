"""professional profiles, privacy, identities and messaging

Revision ID: c4a1f0d92e77
Revises: 8b2d4e6f1a90
Create Date: 2026-11-06 09:00:00.000000

"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c4a1f0d92e77"
down_revision = "8b2d4e6f1a90"
branch_labels = None
depends_on = None


def upgrade():
    # ── profiles: richer presentation fields ──────────────
    with op.batch_alter_table("profiles", schema=None) as batch_op:
        batch_op.add_column(sa.Column("country", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("address", sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column("avatar_path", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("cover_path", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("website_url", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("twitter_url", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("facebook_url", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("cv_filename", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("cv_uploaded_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column("open_to_relocate", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    # ── jobs: explicit remote / hybrid filter ─────────────
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("work_mode", sa.String(length=20), nullable=False, server_default="onsite")
        )
        batch_op.create_index("ix_jobs_work_mode", ["work_mode"], unique=False)

    op.execute("UPDATE jobs SET work_mode = 'remote' WHERE job_type = 'remote'")

    # ── education ─────────────────────────────────────────
    op.create_table(
        "profile_education",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("profile_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("institution", sa.String(length=180), nullable=False),
        sa.Column("degree", sa.String(length=160), nullable=True),
        sa.Column("field_of_study", sa.String(length=160), nullable=True),
        sa.Column("start_year", sa.Integer(), nullable=True),
        sa.Column("end_year", sa.Integer(), nullable=True),
        sa.Column("grade", sa.String(length=80), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("profile_education", schema=None) as batch_op:
        batch_op.create_index("ix_profile_education_profile", ["profile_id"], unique=False)

    # ── work experience ───────────────────────────────────
    op.create_table(
        "profile_experience",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("profile_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("company_name", sa.String(length=180), nullable=False),
        sa.Column("employment_type", sa.String(length=30), nullable=True),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("profile_experience", schema=None) as batch_op:
        batch_op.create_index("ix_profile_experience_profile", ["profile_id"], unique=False)

    # ── skills ────────────────────────────────────────────
    op.create_table(
        "profile_skills",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("profile_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False, server_default="intermediate"),
        sa.Column("years", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "level IN ('beginner','intermediate','advanced','expert')",
            name="ck_profile_skill_level",
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "name", name="uq_profile_skill"),
    )
    with op.batch_alter_table("profile_skills", schema=None) as batch_op:
        batch_op.create_index("ix_profile_skills_profile", ["profile_id"], unique=False)

    # ── languages ─────────────────────────────────────────
    op.create_table(
        "profile_languages",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("profile_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("proficiency", sa.String(length=30), nullable=False, server_default="professional"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "proficiency IN ('basic','conversational','professional','native','fluent')",
            name="ck_profile_language_proficiency",
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "name", name="uq_profile_language"),
    )
    with op.batch_alter_table("profile_languages", schema=None) as batch_op:
        batch_op.create_index("ix_profile_languages_profile", ["profile_id"], unique=False)

    # ── certifications ────────────────────────────────────
    op.create_table(
        "profile_certifications",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("profile_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("issuer", sa.String(length=180), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("credential_id", sa.String(length=160), nullable=True),
        sa.Column("credential_url", sa.String(length=512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("profile_certifications", schema=None) as batch_op:
        batch_op.create_index("ix_profile_certifications_profile", ["profile_id"], unique=False)

    # ── portfolio projects ────────────────────────────────
    op.create_table(
        "profile_projects",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("profile_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("project_url", sa.String(length=512), nullable=True),
        sa.Column("repo_url", sa.String(length=512), nullable=True),
        sa.Column("image_url", sa.String(length=512), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("technologies", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("profile_projects", schema=None) as batch_op:
        batch_op.create_index("ix_profile_projects_profile", ["profile_id"], unique=False)

    # ── privacy ───────────────────────────────────────────
    op.create_table(
        "user_privacy_settings",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column(
            "profile_visibility", sa.String(length=20), nullable=False, server_default="public"
        ),
        sa.Column("show_email", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("show_phone", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("show_location", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_education", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_experience", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_skills", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_languages", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_certifications", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_projects", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_cv", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_messages", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_activity", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "profile_visibility IN ('public','employers','private')",
            name="ck_privacy_visibility",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_privacy_user"),
    )

    # ── external identities ───────────────────────────────
    op.create_table(
        "auth_identities",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False, server_default="google"),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "subject", name="uq_auth_identity_subject"),
    )
    with op.batch_alter_table("auth_identities", schema=None) as batch_op:
        batch_op.create_index("ix_auth_identity_user", ["user_id"], unique=False)

    # ── messaging ─────────────────────────────────────────
    op.create_table(
        "message_threads",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("user_a_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("user_b_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_a_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_b_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_a_id", "user_b_id", name="uq_message_thread_pair"),
    )
    with op.batch_alter_table("message_threads", schema=None) as batch_op:
        batch_op.create_index("ix_message_thread_last", ["last_message_at"], unique=False)

    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("thread_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("sender_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["thread_id"], ["message_threads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.create_index("ix_messages_thread_created", ["thread_id", "created_at"], unique=False)

    # ── backfill from v2.0 data (dialect-neutral) ─────────
    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    users = list(
        bind.execute(
            sa.text(
                "SELECT id, email, google_id, avatar_url FROM users "
                "WHERE id NOT IN (SELECT user_id FROM user_privacy_settings)"
            )
        ).mappings()
    )
    for row in users:
        bind.execute(
            sa.text(
                "INSERT INTO user_privacy_settings "
                "(id, user_id, profile_visibility, show_email, show_phone, show_location, "
                " show_education, show_experience, show_skills, show_languages, "
                " show_certifications, show_projects, show_cv, allow_messages, "
                " show_activity, created_at, updated_at) "
                "VALUES (:id, :user_id, 'public', 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, :now, :now)"
            ),
            {"id": str(uuid.uuid4()), "user_id": row["id"], "now": now},
        )
        if row["google_id"]:
            bind.execute(
                sa.text(
                    "INSERT INTO auth_identities "
                    "(id, user_id, provider, subject, email, avatar_url, last_login_at, "
                    " created_at, updated_at) "
                    "VALUES (:id, :user_id, 'google', :subject, :email, :avatar, :now, :now, :now)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "user_id": row["id"],
                    "subject": row["google_id"],
                    "email": row["email"],
                    "avatar": row["avatar_url"],
                    "now": now,
                },
            )


def downgrade():
    op.drop_table("messages")
    op.drop_table("message_threads")
    op.drop_table("auth_identities")
    op.drop_table("user_privacy_settings")
    op.drop_table("profile_projects")
    op.drop_table("profile_certifications")
    op.drop_table("profile_languages")
    op.drop_table("profile_skills")
    op.drop_table("profile_experience")
    op.drop_table("profile_education")

    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_index("ix_jobs_work_mode")
        batch_op.drop_column("work_mode")

    with op.batch_alter_table("profiles", schema=None) as batch_op:
        batch_op.drop_column("open_to_relocate")
        batch_op.drop_column("cv_uploaded_at")
        batch_op.drop_column("cv_filename")
        batch_op.drop_column("facebook_url")
        batch_op.drop_column("twitter_url")
        batch_op.drop_column("website_url")
        batch_op.drop_column("cover_path")
        batch_op.drop_column("avatar_path")
        batch_op.drop_column("address")
        batch_op.drop_column("country")
