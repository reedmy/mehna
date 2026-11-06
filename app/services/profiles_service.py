"""Profile CRUD, file uploads, completeness and privacy rules.

Every mutating function takes the acting user and the profile being edited and
re-checks ownership, even when the route already did.
"""

from __future__ import annotations

import io
import secrets
from datetime import date, datetime
from pathlib import Path

from flask import current_app
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import (
    Certification,
    Education,
    Language,
    PortfolioProject,
    Profile,
    Skill,
    User,
    UserPrivacySettings,
    WorkExperience,
    utcnow,
)
from app.services.errors import PermissionDenied, ValidationError
from app.utils.security import strip_tags

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_CV_BYTES = 5 * 1024 * 1024
MAX_AVATAR_SIDE = 640
MAX_COVER_WIDTH = 1600
MAX_COVER_HEIGHT = 600

CV_EXTENSIONS = {".pdf", ".doc", ".docx"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

LEVELS = {"beginner", "intermediate", "advanced", "expert"}
PROFICIENCIES = {"basic", "conversational", "professional", "native", "fluent"}
VISIBILITIES = {"public", "employers", "private"}


# ── shared helpers ──────────────────────────────────────


def _text(value, limit: int) -> str | None:
    cleaned = strip_tags(str(value) if value is not None else "").strip()
    return cleaned[:limit] or None


def _url(value, limit: int = 512) -> str | None:
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
        raise ValidationError("يجب أن يبدأ الرابط بـ https:// أو http://")
    return cleaned[:limit]


def _int(value, *, minimum: int = 0, maximum: int = 60) -> int | None:
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("أدخل رقمًا صحيحًا.") from exc
    if number < minimum or number > maximum:
        raise ValidationError(f"القيمة يجب أن تكون بين {minimum} و{maximum}.")
    return number


def _date(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValidationError("صيغة التاريخ غير صحيحة.") from exc


def _year(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        year = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("أدخل سنة صحيحة.") from exc
    if year < 1950 or year > date.today().year + 10:
        raise ValidationError("السنة خارج النطاق المسموح.")
    return year


def _owned_profile(actor: User, profile: Profile) -> None:
    if actor.is_admin:
        return
    if profile.user_id != actor.id:
        raise PermissionDenied()


def _touch(profile: Profile) -> None:
    profile.updated_at = utcnow()


def _sync_legacy(profile: Profile) -> None:
    profile.skills = [row.name for row in profile.skills_list]
    profile.languages = [row.name for row in profile.languages_list]


# ── profile lifecycle ───────────────────────────────────


def get_or_create(user: User) -> Profile:
    # Flush first so rows added by auth/Google flows are visible to the
    # relationship and we never insert a duplicate privacy row.
    db.session.flush()
    profile = user.profile
    if profile is None:
        profile = Profile(user_id=user.id, skills=[], education=[], languages=[])
        db.session.add(profile)
        db.session.flush()
        user.profile = profile
    if user.privacy is None:
        privacy = db.session.scalar(
            db.select(UserPrivacySettings).where(UserPrivacySettings.user_id == user.id)
        )
        if privacy is None:
            privacy = UserPrivacySettings(user_id=user.id)
            db.session.add(privacy)
            db.session.flush()
        user.privacy = privacy
    return profile


def update_basic(actor: User, profile: Profile, data) -> None:
    _owned_profile(actor, profile)

    headline = _text(data.get("headline"), 160)
    bio = _text(data.get("bio"), 4000)
    city = _text(data.get("city"), 80)
    country = _text(data.get("country"), 80) or "العراق"
    address = _text(data.get("address"), 160)

    profile.headline = headline
    profile.bio = bio
    profile.city = city
    profile.country = country
    profile.address = address
    profile.experience_years = _int(data.get("experience_years"), maximum=60) or 0
    profile.github_url = _url(data.get("github_url"), 255)
    profile.linkedin_url = _url(data.get("linkedin_url"), 255)
    profile.portfolio_url = _url(data.get("portfolio_url"), 255)
    profile.website_url = _url(data.get("website_url"), 255)
    profile.twitter_url = _url(data.get("twitter_url"), 255)
    profile.facebook_url = _url(data.get("facebook_url"), 255)
    profile.is_open_to_work = data.get("is_open_to_work") == "1"
    profile.open_to_relocate = data.get("open_to_relocate") == "1"

    cv_url = (data.get("cv_url") or "").strip()
    profile.cv_url = _url(cv_url, 512) if cv_url else None
    _touch(profile)
    db.session.commit()


# ── education ───────────────────────────────────────────


def add_education(actor: User, profile: Profile, data) -> Education:
    _owned_profile(actor, profile)
    institution = _text(data.get("institution"), 180)
    if not institution:
        raise ValidationError("أدخل اسم الجامعة أو المعهد.")
    row = Education(
        profile_id=profile.id,
        institution=institution,
        degree=_text(data.get("degree"), 160),
        field_of_study=_text(data.get("field_of_study"), 160),
        start_year=_year(data.get("start_year")),
        end_year=_year(data.get("end_year")),
        grade=_text(data.get("grade"), 80),
        description=_text(data.get("description"), 1200),
        is_current=data.get("is_current") == "1",
    )
    db.session.add(row)
    _touch(profile)
    db.session.commit()
    return row


def update_education(actor: User, profile: Profile, row_id: str, data) -> Education:
    _owned_profile(actor, profile)
    row = db.session.get(Education, row_id)
    if row is None or row.profile_id != profile.id:
        raise ValidationError("السجل التعليمي غير موجود.")
    institution = _text(data.get("institution"), 180)
    if not institution:
        raise ValidationError("أدخل اسم الجامعة أو المعهد.")
    row.institution = institution
    row.degree = _text(data.get("degree"), 160)
    row.field_of_study = _text(data.get("field_of_study"), 160)
    row.start_year = _year(data.get("start_year"))
    row.end_year = _year(data.get("end_year"))
    row.grade = _text(data.get("grade"), 80)
    row.description = _text(data.get("description"), 1200)
    row.is_current = data.get("is_current") == "1"
    _touch(profile)
    db.session.commit()
    return row


def delete_education(actor: User, profile: Profile, row_id: str) -> None:
    _owned_profile(actor, profile)
    row = db.session.get(Education, row_id)
    if row is None or row.profile_id != profile.id:
        raise ValidationError("السجل التعليمي غير موجود.")
    db.session.delete(row)
    _touch(profile)
    db.session.commit()


# ── work experience ─────────────────────────────────────


def add_experience(actor: User, profile: Profile, data) -> WorkExperience:
    _owned_profile(actor, profile)
    title = _text(data.get("title"), 180)
    company_name = _text(data.get("company_name"), 180)
    if not title or not company_name:
        raise ValidationError("أدخل المسمى الوظيفي واسم الشركة.")
    row = WorkExperience(
        profile_id=profile.id,
        title=title,
        company_name=company_name,
        employment_type=_text(data.get("employment_type"), 30),
        location=_text(data.get("location"), 120),
        start_date=_date(data.get("start_date")),
        end_date=_date(data.get("end_date")),
        is_current=data.get("is_current") == "1",
        description=_text(data.get("description"), 2000),
    )
    db.session.add(row)
    _touch(profile)
    db.session.commit()
    return row


def update_experience(actor: User, profile: Profile, row_id: str, data) -> WorkExperience:
    _owned_profile(actor, profile)
    row = db.session.get(WorkExperience, row_id)
    if row is None or row.profile_id != profile.id:
        raise ValidationError("سجل الخبرة غير موجود.")
    title = _text(data.get("title"), 180)
    company_name = _text(data.get("company_name"), 180)
    if not title or not company_name:
        raise ValidationError("أدخل المسمى الوظيفي واسم الشركة.")
    row.title = title
    row.company_name = company_name
    row.employment_type = _text(data.get("employment_type"), 30)
    row.location = _text(data.get("location"), 120)
    row.start_date = _date(data.get("start_date"))
    row.end_date = _date(data.get("end_date"))
    row.is_current = data.get("is_current") == "1"
    row.description = _text(data.get("description"), 2000)
    _touch(profile)
    db.session.commit()
    return row


def delete_experience(actor: User, profile: Profile, row_id: str) -> None:
    _owned_profile(actor, profile)
    row = db.session.get(WorkExperience, row_id)
    if row is None or row.profile_id != profile.id:
        raise ValidationError("سجل الخبرة غير موجود.")
    db.session.delete(row)
    _touch(profile)
    db.session.commit()


# ── skills ──────────────────────────────────────────────


def add_skill(actor: User, profile: Profile, data) -> Skill:
    _owned_profile(actor, profile)
    name = _text(data.get("name"), 100)
    if not name:
        raise ValidationError("أدخل اسم المهارة.")
    level = (data.get("level") or "intermediate").strip()
    if level not in LEVELS:
        level = "intermediate"
    existing = db.session.scalar(
        db.select(Skill).where(Skill.profile_id == profile.id, Skill.name.ilike(name))
    )
    if existing:
        existing.level = level
        existing.years = _int(data.get("years"), maximum=60)
    else:
        if len(profile.skills_list) >= 30:
            raise ValidationError("يمكنك إضافة 30 مهارة كحد أقصى.")
        profile.skills_list.append(
            Skill(
                name=name,
                level=level,
                years=_int(data.get("years"), maximum=60),
                sort_order=len(profile.skills_list),
            )
        )
    db.session.flush()
    _sync_legacy(profile)
    _touch(profile)
    db.session.commit()
    return db.session.scalar(
        db.select(Skill).where(Skill.profile_id == profile.id, Skill.name == name)
    )


def delete_skill(actor: User, profile: Profile, row_id: str) -> None:
    _owned_profile(actor, profile)
    row = db.session.get(Skill, row_id)
    if row is None or row.profile_id != profile.id:
        raise ValidationError("المهارة غير موجودة.")
    db.session.delete(row)
    db.session.flush()
    db.session.expire(profile, ["skills_list"])
    _sync_legacy(profile)
    _touch(profile)
    db.session.commit()


# ── languages ───────────────────────────────────────────


def add_language(actor: User, profile: Profile, data) -> Language:
    _owned_profile(actor, profile)
    name = _text(data.get("name"), 80)
    if not name:
        raise ValidationError("أدخل اسم اللغة.")
    proficiency = (data.get("proficiency") or "professional").strip()
    if proficiency not in PROFICIENCIES:
        proficiency = "professional"
    existing = db.session.scalar(
        db.select(Language).where(Language.profile_id == profile.id, Language.name.ilike(name))
    )
    if existing:
        existing.proficiency = proficiency
    else:
        profile.languages_list.append(
            Language(
                name=name,
                proficiency=proficiency,
                sort_order=len(profile.languages_list),
            )
        )
    db.session.flush()
    _sync_legacy(profile)
    _touch(profile)
    db.session.commit()
    return db.session.scalar(
        db.select(Language).where(Language.profile_id == profile.id, Language.name == name)
    )


def delete_language(actor: User, profile: Profile, row_id: str) -> None:
    _owned_profile(actor, profile)
    row = db.session.get(Language, row_id)
    if row is None or row.profile_id != profile.id:
        raise ValidationError("اللغة غير موجودة.")
    db.session.delete(row)
    db.session.flush()
    db.session.expire(profile, ["languages_list"])
    _sync_legacy(profile)
    _touch(profile)
    db.session.commit()


# ── certifications ──────────────────────────────────────


def add_certification(actor: User, profile: Profile, data) -> Certification:
    _owned_profile(actor, profile)
    name = _text(data.get("name"), 180)
    if not name:
        raise ValidationError("أدخل اسم الشهادة.")
    row = Certification(
        profile_id=profile.id,
        name=name,
        issuer=_text(data.get("issuer"), 180),
        issue_date=_date(data.get("issue_date")),
        expiry_date=_date(data.get("expiry_date")),
        credential_id=_text(data.get("credential_id"), 160),
        credential_url=_url(data.get("credential_url")),
        description=_text(data.get("description"), 1000),
    )
    db.session.add(row)
    _touch(profile)
    db.session.commit()
    return row


def update_certification(actor: User, profile: Profile, row_id: str, data) -> Certification:
    _owned_profile(actor, profile)
    row = db.session.get(Certification, row_id)
    if row is None or row.profile_id != profile.id:
        raise ValidationError("الشهادة غير موجودة.")
    name = _text(data.get("name"), 180)
    if not name:
        raise ValidationError("أدخل اسم الشهادة.")
    row.name = name
    row.issuer = _text(data.get("issuer"), 180)
    row.issue_date = _date(data.get("issue_date"))
    row.expiry_date = _date(data.get("expiry_date"))
    row.credential_id = _text(data.get("credential_id"), 160)
    row.credential_url = _url(data.get("credential_url"))
    row.description = _text(data.get("description"), 1000)
    _touch(profile)
    db.session.commit()
    return row


def delete_certification(actor: User, profile: Profile, row_id: str) -> None:
    _owned_profile(actor, profile)
    row = db.session.get(Certification, row_id)
    if row is None or row.profile_id != profile.id:
        raise ValidationError("الشهادة غير موجودة.")
    db.session.delete(row)
    _touch(profile)
    db.session.commit()


# ── projects ────────────────────────────────────────────


def add_project(actor: User, profile: Profile, data) -> PortfolioProject:
    _owned_profile(actor, profile)
    title = _text(data.get("title"), 180)
    if not title:
        raise ValidationError("أدخل اسم المشروع.")
    technologies = [
        item.strip()[:60]
        for item in (data.get("technologies") or "").replace("،", ",").split(",")
        if item.strip()
    ][:20]
    row = PortfolioProject(
        profile_id=profile.id,
        title=title,
        description=_text(data.get("description"), 2000),
        project_url=_url(data.get("project_url")),
        repo_url=_url(data.get("repo_url")),
        image_url=_url(data.get("image_url")),
        start_date=_date(data.get("start_date")),
        end_date=_date(data.get("end_date")),
        technologies=technologies,
    )
    db.session.add(row)
    _touch(profile)
    db.session.commit()
    return row


def update_project(actor: User, profile: Profile, row_id: str, data) -> PortfolioProject:
    _owned_profile(actor, profile)
    row = db.session.get(PortfolioProject, row_id)
    if row is None or row.profile_id != profile.id:
        raise ValidationError("المشروع غير موجود.")
    title = _text(data.get("title"), 180)
    if not title:
        raise ValidationError("أدخل اسم المشروع.")
    row.title = title
    row.description = _text(data.get("description"), 2000)
    row.project_url = _url(data.get("project_url"))
    row.repo_url = _url(data.get("repo_url"))
    row.image_url = _url(data.get("image_url"))
    row.start_date = _date(data.get("start_date"))
    row.end_date = _date(data.get("end_date"))
    row.technologies = [
        item.strip()[:60]
        for item in (data.get("technologies") or "").replace("،", ",").split(",")
        if item.strip()
    ][:20]
    _touch(profile)
    db.session.commit()
    return row


def delete_project(actor: User, profile: Profile, row_id: str) -> None:
    _owned_profile(actor, profile)
    row = db.session.get(PortfolioProject, row_id)
    if row is None or row.profile_id != profile.id:
        raise ValidationError("المشروع غير موجود.")
    db.session.delete(row)
    _touch(profile)
    db.session.commit()


# ── privacy ─────────────────────────────────────────────


def get_privacy(user: User) -> UserPrivacySettings:
    db.session.flush()
    privacy = user.privacy
    if privacy is None:
        privacy = db.session.scalar(
            db.select(UserPrivacySettings).where(UserPrivacySettings.user_id == user.id)
        )
        if privacy is None:
            privacy = UserPrivacySettings(user_id=user.id)
            db.session.add(privacy)
        user.privacy = privacy
        db.session.commit()
    return privacy


def update_privacy(actor: User, data) -> UserPrivacySettings:
    privacy = get_privacy(actor)
    visibility = (data.get("profile_visibility") or "public").strip()
    if visibility not in VISIBILITIES:
        visibility = "public"
    privacy.profile_visibility = visibility
    for field in (
        "show_email",
        "show_phone",
        "show_location",
        "show_education",
        "show_experience",
        "show_skills",
        "show_languages",
        "show_certifications",
        "show_projects",
        "show_cv",
        "allow_messages",
        "show_activity",
    ):
        setattr(privacy, field, data.get(field) == "1")
    db.session.commit()
    return privacy


def can_view_profile(target: User, viewer: User | None) -> bool:
    if viewer is not None and (viewer.id == target.id or viewer.is_admin):
        return True
    privacy = target.privacy
    visibility = privacy.profile_visibility if privacy else "public"
    if visibility == "public":
        return True
    if visibility == "employers":
        return bool(viewer and viewer.is_authenticated and viewer.is_employer)
    return False


def can_message(sender: User, target: User) -> bool:
    if sender.id == target.id or not target.is_active:
        return False
    privacy = target.privacy
    if privacy and not privacy.allow_messages:
        return False
    return not (
        privacy and privacy.profile_visibility == "private" and not sender.is_admin
    )


# ── uploads ─────────────────────────────────────────────


def _upload_root() -> Path:
    root = Path(current_app.instance_path) / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _read_image(file_storage) -> Image.Image:
    if file_storage is None or not file_storage.filename:
        raise ValidationError("اختر صورة أولًا.")
    data = file_storage.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise ValidationError("حجم الصورة يجب أن يكون أقل من 5 ميغابايت.")
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValidationError("الملف ليس صورة صالحة.") from exc
    return image.convert("RGB")


def _fit(image: Image.Image, width: int, height: int) -> Image.Image:
    target_ratio = width / height
    source_ratio = image.width / image.height
    if source_ratio > target_ratio:
        new_height = height
        new_width = int(height * source_ratio)
    else:
        new_width = width
        new_height = int(width / source_ratio)
    resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    left = (new_width - width) // 2
    top = (new_height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def save_avatar(actor: User, profile: Profile, file_storage) -> str:
    _owned_profile(actor, profile)
    image = _read_image(file_storage)
    folder = _upload_root() / "avatars"
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{actor.id}.jpg"
    _fit(image, MAX_AVATAR_SIDE, MAX_AVATAR_SIDE).save(folder / filename, "JPEG", quality=88)
    profile.avatar_path = f"avatars/{filename}"
    _touch(profile)
    db.session.commit()
    return profile.avatar_path


def remove_avatar(actor: User, profile: Profile) -> None:
    _owned_profile(actor, profile)
    if profile.avatar_path:
        (_upload_root() / profile.avatar_path).unlink(missing_ok=True)
    profile.avatar_path = None
    _touch(profile)
    db.session.commit()


def save_cover(actor: User, profile: Profile, file_storage) -> str:
    _owned_profile(actor, profile)
    image = _read_image(file_storage)
    folder = _upload_root() / "covers"
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{actor.id}.jpg"
    _fit(image, MAX_COVER_WIDTH, MAX_COVER_HEIGHT).save(folder / filename, "JPEG", quality=85)
    profile.cover_path = f"covers/{filename}"
    _touch(profile)
    db.session.commit()
    return profile.cover_path


def remove_cover(actor: User, profile: Profile) -> None:
    _owned_profile(actor, profile)
    if profile.cover_path:
        (_upload_root() / profile.cover_path).unlink(missing_ok=True)
    profile.cover_path = None
    _touch(profile)
    db.session.commit()


def save_cv(actor: User, profile: Profile, file_storage) -> str:
    _owned_profile(actor, profile)
    if file_storage is None or not file_storage.filename:
        raise ValidationError("اختر ملف السيرة الذاتية.")
    original = secure_filename(file_storage.filename) or "cv"
    suffix = Path(original).suffix.lower()
    if suffix not in CV_EXTENSIONS:
        raise ValidationError("المسموح: PDF أو DOC أو DOCX فقط.")
    data = file_storage.read()
    if len(data) > MAX_CV_BYTES:
        raise ValidationError("حجم الملف يجب أن يكون أقل من 5 ميغابايت.")
    if suffix == ".pdf" and not data.startswith(b"%PDF"):
        raise ValidationError("ملف PDF غير صالح.")
    if suffix == ".docx" and not data.startswith(b"PK"):
        raise ValidationError("ملف DOCX غير صالح.")
    folder = _upload_root() / "cv"
    folder.mkdir(parents=True, exist_ok=True)
    if profile.cv_path:
        (_upload_root() / profile.cv_path).unlink(missing_ok=True)
    filename = f"{actor.id}-{secrets.token_hex(6)}{suffix}"
    (folder / filename).write_bytes(data)
    profile.cv_path = f"cv/{filename}"
    profile.cv_filename = original[:255]
    profile.cv_uploaded_at = datetime.now().astimezone()
    _touch(profile)
    db.session.commit()
    return profile.cv_path


def remove_cv(actor: User, profile: Profile) -> None:
    _owned_profile(actor, profile)
    if profile.cv_path:
        (_upload_root() / profile.cv_path).unlink(missing_ok=True)
    profile.cv_path = None
    profile.cv_filename = None
    profile.cv_uploaded_at = None
    _touch(profile)
    db.session.commit()


def disk_path(relative: str) -> Path:
    """Resolve an upload path and refuse anything outside the upload root."""
    root = _upload_root().resolve()
    candidate = (root / relative).resolve()
    if root not in candidate.parents and candidate != root:
        raise ValidationError("مسار غير صالح.")
    return candidate


def viewer_flags(target: User, viewer: User | None) -> dict:
    privacy = target.privacy or UserPrivacySettings(user_id=target.id)
    privileged = viewer is not None and (viewer.id == target.id or viewer.is_admin)
    visible = can_view_profile(target, viewer)
    # Owner/admin always can message; non-owner uses can_message rules
    if viewer is not None and (viewer.id == target.id or viewer.is_admin):
        can_msg = True
    else:
        can_msg = can_message(viewer, target) if viewer else False
    return {
        "visible": visible,
        "is_owner": bool(viewer and viewer.id == target.id),
        "is_admin": bool(viewer and viewer.is_admin),
        "can_message": can_msg,
        "email": target.email if (privileged or privacy.show_email) else None,
        "phone": target.phone if (privileged or privacy.show_phone) else None,
        "location": (privacy.show_location or privileged),
        "education": visible and (privacy.show_education or privileged),
        "experience": visible and (privacy.show_experience or privileged),
        "skills": visible and (privacy.show_skills or privileged),
        "languages": visible and (privacy.show_languages or privileged),
        "certifications": visible and (privacy.show_certifications or privileged),
        "projects": visible and (privacy.show_projects or privileged),
        "cv": visible and (privacy.show_cv or privileged),
        "activity": visible and (privacy.show_activity or privileged),
    }
