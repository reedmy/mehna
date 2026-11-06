"""Authentication and account lifecycle."""

from __future__ import annotations

from app.extensions import db
from app.models import Profile, User, UserPrivacySettings
from app.models.base import utcnow
from app.models.enums import Role
from app.services.errors import ValidationError
from app.utils.security import normalize_phone, password_problems


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def register(
    *,
    email: str,
    password: str,
    full_name: str,
    role: str = Role.SEEKER.value,
    phone: str | None = None,
) -> User:
    email = normalize_email(email)
    full_name = (full_name or "").strip()

    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValidationError("أدخل بريدًا إلكترونيًا صحيحًا.")
    if len(full_name) < 3:
        raise ValidationError("أدخل اسمك الكامل.")
    problems = password_problems(password)
    if problems:
        raise ValidationError(problems[0])
    if role not in (Role.SEEKER.value, Role.EMPLOYER.value):
        raise ValidationError("نوع الحساب غير صالح.")
    if db.session.scalar(db.select(User).filter_by(email=email)):
        raise ValidationError("هذا البريد مسجّل مسبقًا. جرّب تسجيل الدخول.")

    phone_e164 = normalize_phone(phone) if phone else None
    if phone and not phone_e164:
        raise ValidationError("رقم الهاتف غير صحيح. مثال: 0770 123 4567")

    user = User(
        email=email,
        full_name=full_name,
        role=role,
        phone=phone_e164,
        is_active=True,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()  # assign id before profile FK
    db.session.add(Profile(user_id=user.id, skills=[], education=[], languages=[]))
    db.session.add(UserPrivacySettings(user_id=user.id))
    db.session.commit()
    return user


def authenticate(*, email: str, password: str) -> User | None:
    user = db.session.scalar(db.select(User).filter_by(email=normalize_email(email)))
    if user is None or not user.check_password(password):
        return None
    # Deactivated accounts must not be able to log in (v1 bug).
    if not user.is_active:
        return None
    user.touch_login()
    db.session.commit()
    return user


def demo_account(key: str) -> User | None:
    """Resolve a configured quick-access demo account (dev only)."""
    from flask import current_app

    accounts = current_app.config.get("DEMO_ACCOUNTS") or []
    account = next((a for a in accounts if a.get("key") == key), None)
    if account is None:
        return None
    return db.session.scalar(db.select(User).filter_by(email=str(account.get("email") or "")))


def change_password(user: User, *, current: str, new: str) -> None:
    if not user.check_password(current):
        raise ValidationError("كلمة المرور الحالية غير صحيحة.")
    problems = password_problems(new)
    if problems:
        raise ValidationError(problems[0])
    user.set_password(new)
    db.session.commit()


def set_password(user: User, new: str) -> None:
    """Set a password for an account verified through Google (no current password)."""
    problems = password_problems(new)
    if problems:
        raise ValidationError(problems[0])
    user.set_password(new)
    db.session.commit()


def update_identity(user: User, *, full_name: str | None = None, phone: str | None = None) -> None:
    if full_name is not None:
        if len(full_name.strip()) < 3:
            raise ValidationError("الاسم قصير جدًا.")
        user.full_name = full_name.strip()
    if phone is not None:
        if phone.strip():
            normalized = normalize_phone(phone)
            if not normalized:
                raise ValidationError("رقم الهاتف غير صحيح.")
            user.phone = normalized
        else:
            user.phone = None
    db.session.commit()


def deactivate(user: User) -> None:
    user.is_active = False
    user.phone_verified_at = None
    db.session.commit()


def mark_email_verified(user: User) -> None:
    user.email_verified_at = utcnow()
    db.session.commit()
