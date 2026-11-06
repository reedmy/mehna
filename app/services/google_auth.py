"""Google Sign-In using OAuth 2.0 + OpenID Connect.

Security properties:
- authorisation-code flow on the server (client secret never leaves the server)
- random ``state`` + ``nonce`` stored in the session (CSRF + replay protection)
- PKCE (S256) even for a confidential client
- the returned ID token is validated with Google's official ``google-auth``
  library: signature, issuer, audience, expiry and nonce
- the stable Google ``sub`` is stored in ``auth_identities`` and never used
  an email address alone as proof of ownership
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request

from flask import current_app, url_for
from google.auth import exceptions as google_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.extensions import db
from app.models import AuthIdentity, Profile, User, UserPrivacySettings, utcnow
from app.models.enums import Role

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"
SCOPE = "openid email profile"
TIMEOUT_SECONDS = 10


class GoogleAuthError(Exception):
    def __init__(self, message: str = "تعذّر إكمال الدخول عبر Google. حاول مرة أخرى."):
        self.message = message
        super().__init__(message)


def is_configured() -> bool:
    return bool(
        current_app.config.get("GOOGLE_CLIENT_ID")
        and current_app.config.get("GOOGLE_CLIENT_SECRET")
    )


def redirect_uri() -> str:
    configured = (current_app.config.get("GOOGLE_REDIRECT_URI") or "").strip()
    if configured:
        return configured
    # Deterministic default keeps the value identical whether the app is
    # opened through localhost or 127.0.0.1 (Google requires an exact match).
    site_url = (current_app.config.get("SITE_URL") or "").strip().rstrip("/")
    if site_url:
        return site_url + url_for("auth.google_callback")
    return url_for("auth.google_callback", _external=True)


# ── flow primitives ─────────────────────────────────────


def new_state() -> str:
    return secrets.token_urlsafe(32)


def new_nonce() -> str:
    return secrets.token_urlsafe(32)


def new_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def authorization_url(state: str, *, nonce: str, code_challenge: str) -> str:
    params = {
        "client_id": current_app.config["GOOGLE_CLIENT_ID"],
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": SCOPE,
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "online",
        "prompt": "select_account",
        "include_granted_scopes": "true",
    }
    return f"{AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"


def _read_json(request: urllib.request.Request) -> dict:
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
        current_app.logger.warning("Google OAuth request failed: %s", exc)
        raise GoogleAuthError() from exc


def exchange_code(code: str, code_verifier: str | None = None) -> dict:
    payload = {
        "code": code,
        "client_id": current_app.config["GOOGLE_CLIENT_ID"],
        "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
        "redirect_uri": redirect_uri(),
        "grant_type": "authorization_code",
    }
    if code_verifier:
        payload["code_verifier"] = code_verifier
    request = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=urllib.parse.urlencode(payload).encode(),
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    return _read_json(request)


def verify_id_token(raw_token: str, expected_nonce: str) -> dict:
    """Validate signature/issuer/audience/expiry, then the one-time nonce."""
    if not raw_token:
        raise GoogleAuthError("لم يصل رمز الهوية من Google. حاول مرة أخرى.")
    try:
        claims = google_id_token.verify_oauth2_token(
            raw_token,
            google_requests.Request(),
            current_app.config["GOOGLE_CLIENT_ID"],
        )
    except (ValueError, google_exceptions.GoogleAuthError) as exc:
        current_app.logger.warning("Google ID token rejected: %s", exc)
        raise GoogleAuthError("تعذّر التحقق من حساب Google. حاول مرة أخرى.") from exc

    token_nonce = str(claims.get("nonce") or "")
    if not expected_nonce or not secrets.compare_digest(token_nonce, expected_nonce):
        raise GoogleAuthError("انتهت صلاحية جلسة الدخول. حاول مرة أخرى.")

    if not claims.get("sub"):
        raise GoogleAuthError("لم نستلم معرّف حساب Google.")
    if claims.get("email_verified") is False:
        raise GoogleAuthError("بريد Google غير موثّق. وثّقه ثم أعد المحاولة.")
    return claims


def fetch_profile(access_token: str) -> dict:
    """Fallback userinfo call; the ID token is always the primary source."""
    if not access_token:
        raise GoogleAuthError()
    request = urllib.request.Request(
        USERINFO_ENDPOINT,
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
    )
    return _read_json(request)


# ── account linking / registration ──────────────────────


def _new_profile(user: User) -> None:
    db.session.add(Profile(user_id=user.id, skills=[], education=[], languages=[]))
    db.session.add(UserPrivacySettings(user_id=user.id))


def login_or_register(profile: dict, *, role: str = Role.SEEKER.value) -> User:
    """Find, link, or create the account behind a validated Google profile."""
    google_id = str(profile.get("sub") or "").strip()
    email = (profile.get("email") or "").strip().lower()

    if not google_id or not email:
        raise GoogleAuthError("لم نستلم بريدك من Google. جرّب حسابًا آخر.")
    if profile.get("email_verified") is False:
        raise GoogleAuthError("بريد Google غير موثّق. وثّقه ثم أعد المحاولة.")
    if role not in (Role.SEEKER.value, Role.EMPLOYER.value):
        role = Role.SEEKER.value

    picture = (profile.get("picture") or "")[:512] or None
    now = utcnow()

    # 1) Stable identity association (source of truth).
    identity = db.session.scalar(
        db.select(AuthIdentity).filter_by(provider="google", subject=google_id)
    )
    user = identity.user if identity else None

    # 2) Backwards compatibility with rows created before auth_identities.
    if user is None:
        user = db.session.scalar(db.select(User).filter_by(google_id=google_id))

    # 3) Link an existing verified email account, never an ambiguous one.
    if user is None:
        user = db.session.scalar(db.select(User).filter_by(email=email))
        if user is not None and user.google_id and user.google_id != google_id:
            raise GoogleAuthError(
                "هذا البريد مرتبط بحساب Google آخر. سجّل الدخول بالحساب الصحيح."
            )

    if user is not None and not user.is_active:
        raise GoogleAuthError("هذا الحساب معطّل. تواصل مع الدعم.")

    if user is None:
        full_name = (profile.get("name") or email.split("@")[0]).strip()[:120]
        user = User(
            email=email,
            full_name=full_name or email,
            role=role,
            is_active=True,
            google_id=google_id,
            avatar_url=picture,
            email_verified_at=now,
        )
        # Google-only accounts get an unguessable local password they can
        # replace later through "forgot password".
        user.set_password(secrets.token_urlsafe(32))
        db.session.add(user)
        db.session.flush()
        _new_profile(user)
    else:
        if not user.google_id:
            user.google_id = google_id
        if not user.avatar_url and picture:
            user.avatar_url = picture
        if not user.email_verified_at:
            user.email_verified_at = now
        if user.profile is None:
            _new_profile(user)
        if user.privacy is None:
            db.session.add(UserPrivacySettings(user_id=user.id))

    if identity is None:
        identity = AuthIdentity(
            user_id=user.id,
            provider="google",
            subject=google_id,
            email=email,
            avatar_url=picture,
            last_login_at=now,
        )
        db.session.add(identity)
    else:
        identity.email = email
        if picture:
            identity.avatar_url = picture
        identity.last_login_at = now

    user.touch_login()
    db.session.commit()
    return user
