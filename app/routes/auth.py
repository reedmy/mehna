"""Authentication routes."""

from __future__ import annotations

import secrets

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db, limiter
from app.models import User
from app.services import auth_service, google_auth
from app.services.errors import ValidationError
from app.services.google_auth import GoogleAuthError
from app.utils.security import generate_token, verify_token

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("public.home"))

    role = request.args.get("role") or request.form.get("role") or "seeker"
    if role not in ("seeker", "employer"):
        role = "seeker"

    if request.method == "POST":
        try:
            user = auth_service.register(
                email=request.form.get("email", ""),
                password=request.form.get("password", ""),
                full_name=request.form.get("full_name", ""),
                role=role,
                phone=request.form.get("phone"),
            )
        except ValidationError as exc:
            flash(exc.message, "error")
            return render_template("pages/register.html", role=role, form=request.form), 422

        session.clear()
        login_user(user, remember=False)
        flash("أهلًا بك في مهنة! أكمل ملفك الشخصي ليزيد ظهورك.", "success")
        return redirect(url_for("employer.dashboard" if role == "employer" else "seeker.dashboard"))

    return render_template("pages/register.html", role=role, form={})


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        if request.method == "GET":
            # Give people a clear way to continue, switch account, or log out.
            return render_template("pages/login.html", form={}, next_url="", signed_in=True)
        return redirect(url_for("public.home"))

    next_url = request.args.get("next") or request.form.get("next") or ""

    if request.method == "POST":
        user = auth_service.authenticate(
            email=request.form.get("email", ""),
            password=request.form.get("password", ""),
        )
        if user is None:
            flash("البريد الإلكتروني أو كلمة المرور غير صحيحة.", "error")
            return render_template("pages/login.html", form=request.form, next_url=next_url), 401

        return _login_and_redirect(
            user,
            next_url=next_url,
            remember=request.form.get("remember") == "1",
        )

    return render_template("pages/login.html", form={}, next_url=next_url, signed_in=False)


@bp.post("/login/demo/<account_key>")
@limiter.limit("30 per minute")
def login_demo(account_key: str):
    """One-click sign-in for configured demo accounts (development/testing)."""
    user = auth_service.demo_account(account_key)
    if user is None or not user.is_active:
        flash("تعذّر فتح حساب التجربة. جرّب طريقة الدخول العادية.", "error")
        return redirect(url_for("auth.login"))

    return _login_and_redirect(user)


@bp.get("/auth/google")
@limiter.limit("20 per minute")
def google_start():
    """Send the visitor to Google's account chooser."""
    if current_user.is_authenticated:
        return redirect(url_for("public.home"))
    if not google_auth.is_configured():
        flash(
            "الدخول عبر Google غير مفعّل بعد. "
            "أضف GOOGLE_CLIENT_ID و GOOGLE_CLIENT_SECRET إلى ملف .env.",
            "info",
        )
        return redirect(url_for("auth.login"))

    role = request.args.get("role") or "seeker"
    if role not in ("seeker", "employer"):
        role = "seeker"

    next_url = request.args.get("next") or ""
    if not (next_url.startswith("/") and not next_url.startswith("//")):
        next_url = ""

    state = google_auth.new_state()
    nonce = google_auth.new_nonce()
    verifier, challenge = google_auth.new_pkce_pair()
    session["google_state"] = state
    session["google_nonce"] = nonce
    session["google_pkce"] = verifier
    session["google_role"] = role
    session["google_next"] = next_url
    return redirect(
        google_auth.authorization_url(state, nonce=nonce, code_challenge=challenge)
    )


@bp.get("/auth/google/callback")
def google_callback():
    """Handle Google's redirect: verify state, then sign in or register."""
    error = request.args.get("error")
    if error:
        flash(
            "تم إلغاء الدخول عبر Google."
            if error == "access_denied"
            else "تعذّر الدخول عبر Google.",
            "info" if error == "access_denied" else "error",
        )
        return redirect(url_for("auth.login"))

    expected_state = session.pop("google_state", None)
    expected_nonce = session.pop("google_nonce", None)
    verifier = session.pop("google_pkce", None)
    role = session.pop("google_role", "seeker")
    next_url = session.pop("google_next", "")
    state = request.args.get("state") or ""
    code = request.args.get("code") or ""

    if not expected_state or not state or not secrets.compare_digest(state, expected_state):
        flash("انتهت صلاحية جلسة الدخول. حاول مرة أخرى.", "error")
        return redirect(url_for("auth.login"))
    if not code:
        flash("لم يصل رمز الدخول من Google. حاول مرة أخرى.", "error")
        return redirect(url_for("auth.login"))
    if not expected_nonce:
        flash("انتهت صلاحية جلسة الدخول. حاول مرة أخرى.", "error")
        return redirect(url_for("auth.login"))

    try:
        tokens = google_auth.exchange_code(code, verifier)
        # The ID token is the authority: signature, issuer, audience,
        # expiry and nonce are all validated before any account is touched.
        profile = google_auth.verify_id_token(tokens.get("id_token", ""), expected_nonce)
        user = google_auth.login_or_register(profile, role=role)
    except GoogleAuthError as exc:
        flash(exc.message, "error")
        return redirect(url_for("auth.login"))

    return _login_and_redirect(user, next_url=next_url)


def _login_and_redirect(user, *, next_url: str = "", remember: bool = False) -> str:
    session.clear()
    login_user(user, remember=remember)
    session.permanent = remember
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect(
        url_for(
            "admin.dashboard"
            if user.is_admin
            else "employer.dashboard"
            if user.is_employer
            else "seeker.dashboard"
        )
    )


@bp.post("/auth/switch")
def switch_account():
    """Log out and let the visitor pick another account (Google chooser when available)."""
    logout_user()
    session.clear()
    flash("اختر الحساب الذي تريد الدخول به.", "info")
    if google_auth.is_configured():
        return redirect(url_for("auth.google_start"))
    return redirect(url_for("auth.login"))


@bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    """Account settings available to every role: identity, security, switching."""
    if request.method == "POST":
        try:
            auth_service.update_identity(
                current_user,
                full_name=request.form.get("full_name"),
                phone=request.form.get("phone"),
            )
            flash("تم حفظ بيانات الحساب.", "success")
        except ValidationError as exc:
            db.session.rollback()
            flash(exc.message, "error")
        return redirect(url_for("auth.account"))

    return render_template("pages/account.html")


@bp.post("/account/password")
@login_required
def account_password():
    current = request.form.get("current_password", "")
    new = request.form.get("new_password", "")
    try:
        if current:
            auth_service.change_password(current_user, current=current, new=new)
        elif current_user.google_id:
            # Google-verified session: allow creating a password without the
            # random one generated at signup.
            auth_service.set_password(current_user, new)
        else:
            raise ValidationError("أدخل كلمة المرور الحالية.")
        flash("تم تحديث كلمة المرور.", "success")
    except ValidationError as exc:
        flash(exc.message, "error")
    return redirect(url_for("auth.account"))


@bp.post("/logout")
def logout():
    logout_user()
    session.clear()
    flash("تم تسجيل الخروج.", "info")
    return redirect(url_for("public.home"))


@bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def forgot_password():
    if request.method == "POST":
        email = auth_service.normalize_email(request.form.get("email"))
        user = db.session.scalar(db.select(User).filter_by(email=email))
        if user is not None:
            token = generate_token(user.id)
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            from flask import current_app

            if current_app.config.get("MAIL_SERVER"):
                # Real mail delivery is wired in a later milestone.
                current_app.logger.info("Password reset for %s: %s", email, reset_url)
            else:
                current_app.logger.warning("DEV reset link for %s: %s", email, reset_url)
        # Always the same answer → no account enumeration.
        flash("إذا كان البريد مسجلًا فستصلك رسالة لإعادة التعيين.", "info")
        return redirect(url_for("auth.login"))
    return render_template("pages/forgot_password.html")


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    user_id = verify_token(token, max_age_seconds=3600)
    if user_id is None:
        flash("الرابط منتهي أو غير صالح. اطلب رابطًا جديدًا.", "error")
        return redirect(url_for("auth.forgot_password"))

    user = db.session.get(User, user_id)
    if user is None:
        flash("الحساب غير موجود.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        new_password = request.form.get("password", "")
        if new_password != request.form.get("password_confirm", ""):
            flash("كلمتا المرور غير متطابقتين.", "error")
            return render_template("pages/reset_password.html", token=token), 422
        try:
            user.set_password(new_password)
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("تعذّر تحديث كلمة المرور.", "error")
            return render_template("pages/reset_password.html", token=token), 422
        flash("تم تحديث كلمة المرور. سجّل الدخول.", "success")
        return redirect(url_for("auth.login"))

    return render_template("pages/reset_password.html", token=token)
