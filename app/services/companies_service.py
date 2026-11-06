"""Companies: creation, editing, verification workflow."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Company, User
from app.models.base import utcnow
from app.models.enums import NotificationType, VerificationStatus
from app.services import notifications_service
from app.services.errors import NotFound, PermissionDenied, ValidationError
from app.utils.arabic import slugify
from app.utils.security import strip_tags


def create(owner: User, data: dict) -> Company:
    name = strip_tags(data.get("name"))[:160]
    if len(name) < 2:
        raise ValidationError("أدخل اسم الشركة.")
    if db.session.scalar(
        db.select(Company).where(Company.owner_id == owner.id, Company.name == name)
    ):
        raise ValidationError("لديك شركة بهذا الاسم.")

    company = Company(
        owner_id=owner.id,
        name=name,
        slug=f"{slugify(name)}-{owner.id[:6]}",
        description=strip_tags(data.get("description"))[:4000] or None,
        website=(data.get("website") or "").strip()[:255] or None,
        city=data.get("city") or None,
        industry=data.get("industry") or None,
        size=data.get("size") or None,
        verification_status=VerificationStatus.UNVERIFIED.value,
    )
    db.session.add(company)
    try:
        db.session.commit()
    except IntegrityError as exc:  # pragma: no cover - slug collision is rare
        db.session.rollback()
        raise ValidationError("تعذّر إنشاء الشركة، حاول مرة أخرى.") from exc
    return company


def get_owned(company_id: str, actor: User) -> Company:
    company = db.session.get(Company, company_id)
    if company is None:
        raise NotFound("الشركة غير موجودة.")
    if not actor.is_admin and company.owner_id != actor.id:
        raise PermissionDenied()
    return company


def update(actor: User, company: Company, data: dict) -> Company:
    if not actor.is_admin and company.owner_id != actor.id:
        raise PermissionDenied()
    name = strip_tags(data.get("name"))[:160]
    if len(name) < 2:
        raise ValidationError("أدخل اسم الشركة.")
    company.name = name
    company.description = strip_tags(data.get("description"))[:4000] or None
    company.website = (data.get("website") or "").strip()[:255] or None
    company.city = data.get("city") or None
    company.industry = data.get("industry") or None
    company.size = data.get("size") or None
    db.session.commit()
    return company


def request_verification(actor: User, company: Company, note: str | None = None) -> Company:
    if company.owner_id != actor.id:
        raise PermissionDenied()
    if company.verification_status == VerificationStatus.VERIFIED.value:
        raise ValidationError("الشركة موثّقة بالفعل.")
    company.verification_status = VerificationStatus.PENDING.value
    company.verification_note = (note or "").strip()[:2000] or None
    db.session.commit()
    return company


def verify(admin: User, company: Company) -> Company:
    if not admin.is_admin:
        raise PermissionDenied()
    company.verification_status = VerificationStatus.VERIFIED.value
    company.verified_at = utcnow()
    company.verified_by_id = admin.id
    company.verification_note = None
    notifications_service.notify(
        company.owner,
        type=NotificationType.COMPANY_VERIFIED.value,
        title=f"تم توثيق «{company.name}»",
        body="يمكنك الآن نشر وظائفك مباشرة وستظهر شارة التوثيق للباحثين.",
        link="/employer",
        commit=False,
    )
    db.session.commit()
    return company


def reject(admin: User, company: Company, reason: str | None = None) -> Company:
    if not admin.is_admin:
        raise PermissionDenied()
    company.verification_status = VerificationStatus.REJECTED.value
    company.verification_note = (reason or "لم تُستوفَ شروط التوثيق.")[:2000]
    db.session.commit()
    return company


def set_logo(actor: User, company: Company, logo_url: str) -> Company:
    if company.owner_id != actor.id and not actor.is_admin:
        raise PermissionDenied()
    company.logo_url = logo_url
    db.session.commit()
    return company
