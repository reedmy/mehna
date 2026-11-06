"""Plan limits and entitlements — one place, used by every write path."""

from __future__ import annotations

from flask import current_app

from app.extensions import db
from app.models import Company, Job
from app.models.enums import JobStatus, VerificationStatus


def limits(plan: str | None) -> dict:
    plans = current_app.config["PLAN_LIMITS"]
    return plans.get(plan or "free", plans["free"])


def active_jobs_count(company: Company) -> int:
    return (
        db.session.scalar(
            db.select(db.func.count(Job.id))
            .where(Job.company_id == company.id)
            .where(Job.status.in_([JobStatus.PUBLISHED.value, JobStatus.DRAFT.value]))
        )
        or 0
    )


def can_publish(company: Company) -> tuple[bool, str]:
    """Unverified companies may hold 1 draft job; verified ones follow plan limits."""
    cap = limits(company.owner.plan)["active_jobs"]
    if company.verification_status != VerificationStatus.VERIFIED.value:
        cap = min(cap, 1)
    used = active_jobs_count(company)
    if used >= cap:
        return False, (
            f"وصلت للحد الأقصى ({cap}) من الوظائف في باقتك الحالية. "
            "أرشفة وظيفة أو ترقية الباقة يفتح مجالًا جديدًا."
        )
    return True, ""


def can_add_company(user) -> tuple[bool, str]:
    from app.models import Company as CompanyModel

    owned = (
        db.session.scalar(
            db.select(db.func.count(CompanyModel.id)).where(CompanyModel.owner_id == user.id)
        )
        or 0
    )
    if owned >= limits(user.plan)["team_members"]:
        return False, "وصلت للحد الأقصى من الشركات في باقتك."
    return True, ""
