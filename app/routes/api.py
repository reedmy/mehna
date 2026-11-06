"""Small JSON/HTMX endpoints: notifications, save, report."""

from __future__ import annotations

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Job
from app.models.enums import REPORT_REASON_LABELS
from app.services import engagement_service, jobs_service, notifications_service

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/notifications")
@login_required
def notifications():
    items = notifications_service.list_for(current_user)
    unread = notifications_service.unread_count(current_user)
    if request.headers.get("HX-Request"):
        return render_template("components/_notification_list.html", items=items)
    return jsonify(
        {
            "unread": unread,
            "items": [
                {
                    "id": n.id,
                    "title": n.title,
                    "body": n.body,
                    "link": n.link,
                    "is_read": n.is_read,
                    "created_at": n.created_at.isoformat(),
                }
                for n in items
            ],
        }
    )


@bp.get("/notifications/count")
@login_required
def notifications_count():
    count = notifications_service.unread_count(current_user)
    if request.headers.get("HX-Request"):
        return render_template("components/_notification_badge.html", count=count)
    return jsonify({"count": count})


@bp.post("/notifications/read-all")
@login_required
def notifications_read_all():
    notifications_service.mark_all_read(current_user)
    if request.headers.get("HX-Request"):
        return render_template("components/_notification_badge.html", count=0)
    return jsonify({"ok": True})


@bp.post("/jobs/<job_id>/save")
@login_required
def toggle_save(job_id: str):
    job = db.session.get(Job, job_id)
    if job is None:
        abort(404)
    saved = engagement_service.toggle_save(current_user, job)
    if request.headers.get("HX-Request"):
        return render_template("components/_save_button.html", job=job, saved=saved)
    return jsonify({"saved": saved})


@bp.post("/jobs/<job_id>/report")
@login_required
def report_job(job_id: str):
    job = db.session.get(Job, job_id)
    if job is None:
        abort(404)
    engagement_service.report_job(
        current_user, job, request.form.get("reason", ""), request.form.get("details")
    )
    from flask import flash

    flash("وصلنا بلاغك، شكرًا لمساعدتنا في حماية الباحثين.", "success")
    return redirect(url_for("public.job_detail", job_id=job.id, slug=job.slug))


@bp.get("/reasons")
def reasons():
    return jsonify(REPORT_REASON_LABELS)


@bp.get("/jobs/search")
def quick_search():
    q = request.args.get("q", "")
    results = jobs_service.search({"q": q}, per_page=5)
    return render_template("components/_search_results.html", pagination=results)
