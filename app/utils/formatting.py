"""Jinja filters: money, dates, relative time."""

from __future__ import annotations

from datetime import datetime, timezone

CURRENCY_LABELS = {"IQD": "د.ع", "USD": "$"}

AR_MONTHS = [
    "كانون الثاني",
    "شباط",
    "آذار",
    "نيسان",
    "أيار",
    "حزيران",
    "تموز",
    "آب",
    "أيلول",
    "تشرين الأول",
    "تشرين الثاني",
    "كانون الأول",
]


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def money(value, currency: str = "IQD") -> str:
    if value is None or value == "":
        return "—"
    try:
        amount = int(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{amount:,} {CURRENCY_LABELS.get(currency, currency)}"


def date_ar(dt: datetime | None) -> str:
    dt = _aware(dt)
    if not dt:
        return "—"
    return f"{dt.day} {AR_MONTHS[dt.month - 1]} {dt.year}"


def relative_time(dt: datetime | None) -> str:
    dt = _aware(dt)
    if not dt:
        return "—"
    delta = datetime.now(timezone.utc) - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "الآن"
    minutes = seconds // 60
    if minutes < 60:
        return f"قبل {minutes} دقيقة" if minutes > 1 else "قبل دقيقة"
    hours = minutes // 60
    if hours < 24:
        return f"قبل {hours} ساعة" if hours > 1 else "قبل ساعة"
    days = hours // 24
    if days < 30:
        return f"قبل {days} يوم" if days > 1 else "قبل يوم"
    months = days // 30
    if months < 12:
        return f"قبل {months} شهر" if months > 1 else "قبل شهر"
    years = months // 12
    return f"قبل {years} سنة" if years > 1 else "قبل سنة"


def initials(name: str | None) -> str:
    parts = [p for p in (name or "").split() if p]
    return "".join(p[0] for p in parts[:2]) if parts else "؟"
