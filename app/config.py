"""Application configuration.

Everything is driven by environment variables with safe development defaults.
Production must set SECRET_KEY and DATABASE_URL explicitly (see .env.example).
"""

from __future__ import annotations

import os
from datetime import timedelta


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        # Local development: SQLite inside instance/ (zero setup on Windows).
        return "sqlite:///mehna.db"
    # Heroku/Render style URLs still arrive as postgres://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    # ── Core ─────────────────────────────────────────────
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-key-change-me")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # ── Session / cookies ────────────────────────────────
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(days=14)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # ── CSRF ─────────────────────────────────────────────
    WTF_CSRF_TIME_LIMIT = 60 * 60 * 8

    # ── Rate limiting ────────────────────────────────────
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_DEFAULT = "600 per hour"

    # ── Reverse proxy (Cloudflare tunnel, nginx, ...) ────
    TRUSTED_PROXY_COUNT = int(os.getenv("TRUSTED_PROXY_COUNT", "0"))

    # ── Google Sign-In (OAuth 2.0 / OpenID Connect) ──────
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    # Leave empty to derive it from the request (recommended in dev).
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "").strip()

    # ── Mail ─────────────────────────────────────────────
    MAIL_SERVER = os.getenv("MAIL_SERVER", "")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_SENDER = os.getenv("MAIL_SENDER", "no-reply@mehna.iq")
    MAIL_USE_TLS = _env_bool("MAIL_USE_TLS", True)

    # ── Brand / product ──────────────────────────────────
    SITE_NAME = os.getenv("SITE_NAME", "مهنة")
    SITE_URL = os.getenv("SITE_URL", "http://localhost:5000")
    DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "IQD")

    # ── Business rules (single source of truth) ──────────
    PLAN_LIMITS = {
        "free": {"active_jobs": 1, "featured_jobs": 0, "team_members": 1},
        "pro": {"active_jobs": 15, "featured_jobs": 3, "team_members": 5},
        "business": {"active_jobs": 100, "featured_jobs": 15, "team_members": 25},
    }
    JOB_EXPIRY_DAYS = 45
    JOBS_PER_PAGE = 12
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB uploads

    # Quick demo-access accounts rendered on /login when configured.
    # Production must leave this list empty (see ProductionConfig).
    DEMO_ACCOUNTS: list[dict] = [
        {
            "key": "seeker",
            "label": "باحث عن عمل",
            "email": "seeker@mehna.iq",
            "password": "Seeker@1234",
        },
        {
            "key": "employer",
            "label": "صاحب عمل",
            "email": "hr@rafidain-tech.iq",
            "password": "Employer@1234",
        },
        {
            "key": "admin",
            "label": "مسؤول النظام",
            "email": "admin@mehna.iq",
            "password": "Admin@1234",
        },
    ]


class DevelopmentConfig(Config):
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret-key"
    DEMO_ACCOUNTS = [
        {
            "key": "seeker",
            "label": "باحث عن عمل",
            "email": "seeker@test.iq",
            "password": "Passw0rd!",
        }
    ]
    GOOGLE_CLIENT_ID = "test-client-id"
    GOOGLE_CLIENT_SECRET = "test-client-secret"


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = "https"
    DEMO_ACCOUNTS = []  # No quick-access demo accounts in production.


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
