"""Security helpers: tokens, sanitising, phone normalisation, password policy."""

from __future__ import annotations

import re
import secrets

import bleach
import phonenumbers
from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

ALLOWED_TAGS = ["b", "strong", "i", "em", "u", "p", "br", "ul", "ol", "li"]
ALLOWED_ATTRS: dict[str, list[str]] = {}

MIN_PASSWORD_LENGTH = 8


def sanitize_html(raw: str | None) -> str:
    """Allow a tiny, safe subset of markup (job descriptions)."""
    if not raw:
        return ""
    return bleach.clean(raw, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)


def strip_tags(raw: str | None) -> str:
    if not raw:
        return ""
    return bleach.clean(raw, tags=[], attributes={}, strip=True).strip()


def normalize_phone(raw: str | None, region: str = "IQ") -> str | None:
    """Return E.164 (+9647XXXXXXXX) or None when the number is invalid."""
    if not raw:
        return None
    cleaned = strip_tags(str(raw))
    # Convert Arabic-Indic digits before parsing.
    cleaned = cleaned.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    digits = re.sub(r"[^\d+]", "", cleaned)
    if not digits:
        return None
    try:
        parsed = phonenumbers.parse(digits, region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def password_problems(password: str) -> list[str]:
    problems: list[str] = []
    if len(password or "") < MIN_PASSWORD_LENGTH:
        problems.append(f"كلمة المرور يجب أن تكون {MIN_PASSWORD_LENGTH} أحرف على الأقل")
    if not re.search(r"[A-Za-z\u0600-\u06FF]", password or ""):
        problems.append("أضف حرفًا واحدًا على الأقل")
    if not re.search(r"\d", password or ""):
        problems.append("أضف رقمًا واحدًا على الأقل")
    return problems


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="mehna-v2")


def generate_token(payload: str) -> str:
    return _serializer().dumps(payload)


def verify_token(token: str, max_age_seconds: int = 3600) -> str | None:
    try:
        return _serializer().loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None


def new_api_token() -> str:
    return secrets.token_urlsafe(32)
