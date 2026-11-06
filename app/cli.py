"""CLI commands: seed demo data, create admin, expire jobs."""

from __future__ import annotations

from datetime import date, timedelta

import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models import (
    Application,
    AuthIdentity,
    Certification,
    Company,
    Education,
    Job,
    Language,
    Message,
    MessageThread,
    PortfolioProject,
    Profile,
    Skill,
    User,
    UserPrivacySettings,
    WorkExperience,
)
from app.models.base import utcnow
from app.models.enums import ApplicationStatus, JobStatus, JobType, VerificationStatus
from app.services import jobs_service


@click.command("seed")
@click.option("--force", is_flag=True, help="حذف البيانات الحالية أولًا")
@with_appcontext
def seed(force: bool):
    """Populate a development database with realistic Arabic demo data."""
    if force:
        for model in (
            Message,
            MessageThread,
            AuthIdentity,
            Certification,
            PortfolioProject,
            WorkExperience,
            Education,
            Skill,
            Language,
            UserPrivacySettings,
            Application,
            Job,
            Company,
            Profile,
            User,
        ):
            db.session.query(model).delete()
        db.session.commit()
    elif db.session.scalar(db.select(db.func.count(User.id))):
        click.echo("قاعدة البيانات غير فارغة. استخدم --force لإعادة التهيئة.")
        return

    admin = _user("admin@mehna.iq", "Admin@1234", "مدير المنصة", "admin")
    seeker = _user("seeker@mehna.iq", "Seeker@1234", "علي حسين الجبوري", "seeker")
    seeker_profile = seeker.profile
    seeker_profile.headline = "مطوّر ويب — Python وFlask"
    seeker_profile.city = "بغداد"
    seeker_profile.country = "العراق"
    seeker_profile.experience_years = 3
    seeker_profile.skills = ["Python", "Flask", "PostgreSQL", "HTML/CSS", "Git"]
    seeker_profile.bio = (
        "مطوّر ويب أهتم ببناء تطبيقات سريعة وسهلة الاستخدام، خبرة في Flask وقواعد البيانات. "
        "أبحث عن فرصة عمل بدوام كامل في بغداد أو عن بُعد."
    )
    seeker_profile.linkedin_url = "https://linkedin.com/in/ali-example"
    seeker_profile.github_url = "https://github.com/ali-example"
    seeker_profile.is_open_to_work = True
    db.session.add_all(
        [
            Skill(profile_id=seeker_profile.id, name=name, level=level, sort_order=index)
            for index, (name, level) in enumerate(
                [
                    ("Python", "expert"),
                    ("Flask", "advanced"),
                    ("PostgreSQL", "advanced"),
                    ("HTML/CSS", "advanced"),
                    ("Git", "advanced"),
                ]
            )
        ]
    )
    db.session.add_all(
        [
            Language(
                profile_id=seeker_profile.id,
                name="العربية",
                proficiency="native",
                sort_order=0,
            ),
            Language(
                profile_id=seeker_profile.id,
                name="الإنجليزية",
                proficiency="professional",
                sort_order=1,
            ),
        ]
    )
    db.session.add(
        Education(
            profile_id=seeker_profile.id,
            institution="جامعة بغداد",
            degree="بكالوريوس",
            field_of_study="علوم الحاسوب",
            start_year=2018,
            end_year=2022,
            grade="جيد جدًا",
        )
    )
    db.session.add(
        WorkExperience(
            profile_id=seeker_profile.id,
            title="مطوّر Backend",
            company_name="شركة نهر التقنية",
            employment_type="full_time",
            location="بغداد",
            start_date=date(utcnow().year - 2, 1, 1),
            is_current=True,
            description="بناء واجهات API وربط قواعد البيانات وتطوير ميزات المنتج.",
        )
    )
    db.session.commit()

    employers = [
        ("hr@rafidain-tech.iq", "شركة الرافدين للتقنية", "بغداد", "تقنية المعلومات", "51-200"),
        ("jobs@basra-energy.iq", "بصرة للطاقة", "البصرة", "النفط والغاز", "500+"),
        ("careers@erbil-bank.iq", "مصرف أربيل التجاري", "أربيل", "المصارف والمال", "201-500"),
    ]
    companies = []
    for email, name, city, industry, size in employers:
        owner = _user(email, "Employer@1234", f"مسؤول التوظيف — {name}", "employer")
        company = Company(
            owner_id=owner.id,
            name=name,
            slug=f"company-{len(companies) + 1}",
            description=f"{name} — من المؤسسات الرائدة في قطاع {industry} في العراق.",
            city=city,
            industry=industry,
            size=size,
            website="https://example.iq",
            verification_status=VerificationStatus.VERIFIED.value,
            verified_at=utcnow(),
            verified_by_id=admin.id,
        )
        db.session.add(company)
        companies.append(company)
    db.session.commit()

    jobs_data = [
        ("مطوّر Backend — Python", "بغداد", JobType.FULL_TIME.value, "mid", 1500000, 2500000),
        ("محاسب أول", "بغداد", JobType.FULL_TIME.value, "senior", 1200000, 1800000),
        ("مهندس نفط — موقع البصرة", "البصرة", JobType.FULL_TIME.value, "mid", 2000000, 3500000),
        ("مسؤول خدمة عملاء", "أربيل", JobType.FULL_TIME.value, "entry", 700000, 1000000),
        ("مصمم واجهات UI/UX", "بغداد", JobType.REMOTE.value, "mid", 1300000, 2000000),
        ("أخصائي موارد بشرية", "الموصل", JobType.FULL_TIME.value, "junior", 800000, 1200000),
        ("فني كهرباء", "كربلاء", JobType.CONTRACT.value, "junior", 600000, 900000),
        ("محلل بيانات", "بغداد", JobType.FULL_TIME.value, "senior", 1800000, 2800000),
        ("سائق توصيل", "النجف", JobType.PART_TIME.value, "entry", 500000, 700000),
        ("مدير مشروع تقني", "أربيل", JobType.FULL_TIME.value, "lead", 3000000, 4500000),
        ("متدرب تسويق رقمي", "بغداد", JobType.INTERNSHIP.value, "entry", 300000, 500000),
        ("مطوّر تطبيقات موبايل", "البصرة", JobType.FREELANCE.value, "mid", 1400000, 2200000),
    ]

    for index, (title, city, job_type, level, low, high) in enumerate(jobs_data):
        company = companies[index % len(companies)]
        job = Job(
            company_id=company.id,
            posted_by_id=company.owner_id,
            title=title,
            slug=f"{title.replace(' ', '-')}-{index}",
            description=(
                f"نبحث عن {title} للانضمام إلى فريقنا في {city}. "
                "المهام تشمل العمل مع فريق متعدد التخصصات، متابعة المؤشرات، "
                "وتقديم حلول عملية تساهم في نمو الأعمال."
            ),
            requirements=["خبرة عملية ذات صلة", "مهارات تواصل جيدة", "إجادة العربية"],
            benefits=["تأمين صحي", "بيئة عمل مرنة", "فرص تدريب"],
            city=city,
            job_type=job_type,
            work_mode=(
                "remote"
                if job_type == JobType.REMOTE.value
                else "hybrid"
                if index % 4 == 0
                else "onsite"
            ),
            career_level=level,
            experience_years_min=1 if level in ("entry", "junior") else 3,
            salary_min=low,
            salary_max=high,
            salary_negotiable=False,
            status=JobStatus.PUBLISHED.value,
            is_featured=index < 3,
            published_at=utcnow() - timedelta(days=index),
            expires_at=utcnow() + timedelta(days=45 - index),
        )
        db.session.add(job)
        db.session.flush()
        job.refresh_search_fields()

    db.session.commit()

    first_job = db.session.scalar(db.select(Job).limit(1))
    if first_job:
        db.session.add(
            Application(
                job_id=first_job.id,
                seeker_id=seeker.id,
                cover_letter="أرغب بالانضمام لفريقكم، لدي خبرة 3 سنوات في تطوير الويب.",
                status=ApplicationStatus.SHORTLISTED.value,
            )
        )
        db.session.commit()

    # A real conversation makes the messages area demonstrable end-to-end.
    first_employer = db.session.scalar(db.select(User).filter_by(email="hr@rafidain-tech.iq"))
    if first_employer is not None:
        a, b = sorted((seeker.id, first_employer.id))
        thread = MessageThread(user_a_id=a, user_b_id=b, last_message_at=utcnow())
        db.session.add(thread)
        db.session.flush()
        db.session.add(
            Message(
                thread_id=thread.id,
                sender_id=first_employer.id,
                body="مرحبًا علي، اطلعنا على ملفك ونود ترتيب مقابلة قصيرة هذا الأسبوع.",
            )
        )
        db.session.commit()

    click.echo("✔ تم إنشاء بيانات تجريبية:")
    click.echo("  admin@mehna.iq / Admin@1234")
    click.echo("  seeker@mehna.iq / Seeker@1234")
    click.echo("  hr@rafidain-tech.iq / Employer@1234")


@click.command("create-admin")
@click.option("--email", prompt=True)
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@click.option("--name", prompt="الاسم الكامل")
@with_appcontext
def create_admin(email: str, password: str, name: str):
    """Create (or promote) an administrator."""
    email = email.strip().lower()
    user = db.session.scalar(db.select(User).filter_by(email=email))
    if user:
        user.role = "admin"
        user.is_active = True
        user.set_password(password)
        db.session.commit()
        click.echo(f"تم ترقية {email} إلى مدير.")
        return
    user = User(email=email, full_name=name, role="admin", is_active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    db.session.add(Profile(user_id=user.id, skills=[], education=[]))
    db.session.add(UserPrivacySettings(user_id=user.id))
    db.session.commit()
    click.echo(f"تم إنشاء المدير {email}.")


@click.command("expire-jobs")
@with_appcontext
def expire_jobs():
    """Close jobs whose expiry date has passed (cron-friendly)."""
    count = jobs_service.expire_stale()
    click.echo(f"تم إنهاء {count} وظيفة منتهية.")


def _user(email: str, password: str, name: str, role: str) -> User:
    user = User(email=email, full_name=name, role=role, is_active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    db.session.add(Profile(user_id=user.id, skills=[], education=[], languages=["العربية"]))
    db.session.add(UserPrivacySettings(user_id=user.id))
    db.session.commit()
    return user
