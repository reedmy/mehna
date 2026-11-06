"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from app import create_app
from app.extensions import db
from app.models import Company, Job, Profile, User
from app.models.base import utcnow
from app.models.enums import JobStatus, VerificationStatus


@pytest.fixture()
def app():
    application = create_app("testing")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def session(app):
    return db.session


def make_user(
    email: str,
    role: str = "seeker",
    password: str = "Passw0rd!",
    active: bool = True,
    phone: str | None = "+9647701234567",
) -> User:
    user = User(
        email=email,
        full_name=f"مستخدم {email.split('@')[0]}",
        role=role,
        is_active=active,
        phone=phone,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    db.session.add(Profile(user_id=user.id, skills=["Python"], education=[]))
    db.session.commit()
    return user


def make_company(owner: User, name: str = "شركة اختبار", verified: bool = True) -> Company:
    company = Company(
        owner_id=owner.id,
        name=name,
        slug=f"company-{owner.id[:6]}",
        city="بغداد",
        industry="تقنية المعلومات",
        verification_status=(
            VerificationStatus.VERIFIED.value if verified else VerificationStatus.UNVERIFIED.value
        ),
        verified_at=utcnow() if verified else None,
    )
    db.session.add(company)
    db.session.commit()
    return company


def make_job(
    company: Company, title: str = "مطوّر Python", status: str = JobStatus.PUBLISHED.value
) -> Job:
    job = Job(
        company_id=company.id,
        posted_by_id=company.owner_id,
        title=title,
        slug=f"job-{title[:6]}-{company.id[:6]}",
        description="وصف وظيفة تجريبي طويل بما يكفي لاجتياز التحقق.",
        city="بغداد",
        status=status,
        published_at=utcnow(),
        salary_min=1000000,
        salary_max=2000000,
        salary_negotiable=False,
    )
    db.session.add(job)
    db.session.flush()
    job.refresh_search_fields()
    db.session.commit()
    return job


def login(client, email: str, password: str = "Passw0rd!"):
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)


@pytest.fixture()
def users(app):
    return {
        "seeker": make_user("seeker@test.iq", "seeker"),
        "employer": make_user("employer@test.iq", "employer"),
        "other_employer": make_user("other@test.iq", "employer"),
        "admin": make_user("admin@test.iq", "admin"),
    }


@pytest.fixture()
def user_with_profile(app):
    """Create a seeker user with a profile."""
    user = make_user("profileuser@test.iq", "seeker")
    # Ensure profile exists
    from app.services.profiles_service import get_or_create
    profile = get_or_create(user)
    # Add some basic content
    from app.services.profiles_service import update_basic
    update_basic(user, profile, {
        "headline": "مهندس برامج",
        "bio": "مطور مبتدئ يحب التعلم",
        "city": "بغداد",
        "country": "العراق",
        "experience_years": 2,
    })
    db.session.commit()
    return user


@pytest.fixture()
def another_user(app):
    """Create another user (different role) for testing."""
    user = make_user("another@test.iq", "seeker")
    from app.services.profiles_service import get_or_create, update_privacy
    get_or_create(user)
    update_privacy(user, {
        "profile_visibility": "public",
        "allow_messages": "1",
        "show_email": "1",
        "show_phone": "1",
        "show_location": "1",
        "show_education": "1",
        "show_experience": "1",
        "show_skills": "1",
        "show_languages": "1",
        "show_certifications": "1",
        "show_projects": "1",
        "show_cv": "1",
        "show_activity": "1",
    })
    db.session.commit()
    return user
