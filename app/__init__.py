"""Mehna v2 — application factory."""

from __future__ import annotations

import os

from flask import Flask, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import CONFIG_MAP, Config
from app.extensions import csrf, db, limiter, login_manager, migrate


def create_app(config: str | type[Config] | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    if config is None:
        config = os.getenv("FLASK_ENV", "development")
    if isinstance(config, str):
        config = CONFIG_MAP.get(config, Config)

    app.config.from_object(config)
    os.makedirs(app.instance_path, exist_ok=True)

    _init_extensions(app)
    _register_blueprints(app)
    _register_errors(app)
    _register_jinja(app)
    _register_cli(app)
    _register_health(app)

    return app


# ── wiring ────────────────────────────────────────────────


def _init_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    csrf.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

    proxies = app.config.get("TRUSTED_PROXY_COUNT", 0)
    if proxies:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxies, x_proto=proxies, x_host=proxies)


def _register_blueprints(app: Flask) -> None:
    from app.routes import admin, api, auth, employer, messages, profiles, public, seeker

    app.register_blueprint(public.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(profiles.bp)
    app.register_blueprint(messages.bp)
    app.register_blueprint(seeker.bp)
    app.register_blueprint(employer.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(api.bp)


def _register_errors(app: Flask) -> None:
    from flask import flash, redirect, url_for

    from app.services.errors import DomainError

    @app.errorhandler(DomainError)
    def domain_error(exc: DomainError):
        flash(exc.message, "error")
        back = request.referrer or url_for("public.home")
        return redirect(back)

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/error.html", code=403, title="غير مسموح"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/error.html", code=404, title="الصفحة غير موجودة"), 404

    @app.errorhandler(413)
    def too_large(_e):
        return render_template("errors/error.html", code=413, title="الملف كبير جدًا"), 413

    @app.errorhandler(429)
    def rate_limited(_e):
        return render_template("errors/error.html", code=429, title="محاولات كثيرة"), 429

    @app.errorhandler(500)
    def server_error(_e):
        db.session.rollback()
        return render_template("errors/error.html", code=500, title="خطأ غير متوقع"), 500


def _register_jinja(app: Flask) -> None:
    from app.models.enums import (
        APPLICATION_STATUS_LABELS,
        APPLICATION_STATUS_TONE,
        CAREER_LEVEL_LABELS,
        JOB_STATUS_LABELS,
        JOB_TYPE_LABELS,
        REPORT_REASON_LABELS,
        ROLE_LABELS,
        VERIFICATION_LABELS,
        WORK_MODE_LABELS,
    )
    from app.utils import formatting

    @app.context_processor
    def inject_globals():
        from flask_login import current_user

        unread = 0
        unread_messages = 0
        pending_companies = 0
        open_reports = 0
        if current_user.is_authenticated:
            from app.services import messaging_service, notifications_service

            unread = notifications_service.unread_count(current_user)
            unread_messages = messaging_service.unread_count(current_user)
            if current_user.is_admin:
                from app.models import Company, JobReport
                from app.models.enums import ReportStatus, VerificationStatus

                pending_companies = (
                    db.session.scalar(
                        db.select(db.func.count(Company.id)).where(
                            Company.verification_status == VerificationStatus.PENDING.value
                        )
                    )
                    or 0
                )
                open_reports = (
                    db.session.scalar(
                        db.select(db.func.count(JobReport.id)).where(
                            JobReport.status == ReportStatus.OPEN.value
                        )
                    )
                    or 0
                )

        return {
            "current_user": current_user,
            "site_name": app.config["SITE_NAME"],
            "site_url": app.config["SITE_URL"],
            "unread_notifications": unread,
            "unread_messages": unread_messages,
            "pending_companies": pending_companies,
            "open_reports": open_reports,
            "status_labels": APPLICATION_STATUS_LABELS,
            "status_tones": APPLICATION_STATUS_TONE,
            "job_type_labels": JOB_TYPE_LABELS,
            "level_labels": CAREER_LEVEL_LABELS,
            "job_status_labels": JOB_STATUS_LABELS,
            "verification_labels": VERIFICATION_LABELS,
            "report_reason_labels": REPORT_REASON_LABELS,
            "role_labels": ROLE_LABELS,
            "work_mode_labels": WORK_MODE_LABELS,
        }

    app.jinja_env.filters["money"] = formatting.money
    app.jinja_env.filters["relative_time"] = formatting.relative_time
    app.jinja_env.filters["date_ar"] = formatting.date_ar
    app.jinja_env.filters["initials"] = formatting.initials
    app.jinja_env.filters["job_type_label"] = lambda value: JOB_TYPE_LABELS.get(
        value, value or "—"
    )
    app.jinja_env.filters["work_mode_label"] = lambda value: WORK_MODE_LABELS.get(
        value, value or "—"
    )
    app.jinja_env.filters["employment_type_label"] = lambda value: JOB_TYPE_LABELS.get(
        value, value or "—"
    )
    app.jinja_env.filters["level_label"] = lambda value: CAREER_LEVEL_LABELS.get(
        value, value or "—"
    )


def _register_cli(app: Flask) -> None:
    from app import cli

    app.cli.add_command(cli.seed)
    app.cli.add_command(cli.create_admin)
    app.cli.add_command(cli.expire_jobs)


def _register_health(app: Flask) -> None:
    @app.get("/health")
    def health():
        from sqlalchemy import text

        try:
            db.session.execute(text("SELECT 1"))
            db_ok = True
        except Exception:  # pragma: no cover - defensive
            db_ok = False
        payload = {"status": "ok" if db_ok else "degraded", "db": db_ok, "version": "2.0.0"}
        return jsonify(payload), (200 if db_ok else 503)

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        return response
