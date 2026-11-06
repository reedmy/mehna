"""Google Sign-In: state handling, account linking, and safety checks."""

from __future__ import annotations

import urllib.parse

from app.extensions import db
from app.models import User
from app.services import google_auth
from tests.conftest import make_user


def _profile(**overrides):
    data = {
        "sub": "google-123",
        "email": "noura@gmail.com",
        "email_verified": True,
        "name": "نورة علي",
        "picture": "https://example.com/a.png",
    }
    data.update(overrides)
    return data


def test_google_start_redirects_with_state(client):
    response = client.get("/auth/google")
    assert response.status_code == 302
    location = response.headers["Location"]
    assert location.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    query = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
    assert query["client_id"] == ["test-client-id"]
    assert query["redirect_uri"] == ["http://localhost:5000/auth/google/callback"]
    assert query["prompt"] == ["select_account"]
    with client.session_transaction() as session:
        assert session["google_state"] == query["state"][0]


def test_google_callback_rejects_bad_state(client):
    client.get("/auth/google")
    response = client.get("/auth/google/callback?state=wrong&code=abc", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_google_callback_creates_account(app, client, monkeypatch):
    monkeypatch.setattr(
        google_auth, "exchange_code", lambda code, verifier=None: {"id_token": "fake-id-token"}
    )
    monkeypatch.setattr(google_auth, "verify_id_token", lambda token, nonce: _profile())

    start = client.get("/auth/google")
    query = urllib.parse.parse_qs(urllib.parse.urlparse(start.headers["Location"]).query)
    state = query["state"][0]
    response = client.get(f"/auth/google/callback?state={state}&code=abc", follow_redirects=False)

    assert response.status_code == 302
    user = db.session.scalar(db.select(User).filter_by(email="noura@gmail.com"))
    assert user is not None
    assert user.google_id == "google-123"
    assert user.profile is not None
    assert user.privacy is not None
    assert user.email_verified_at is not None
    assert user.auth_identities and user.auth_identities[0].subject == "google-123"
    assert client.get("/dashboard/").status_code == 200


def test_google_links_existing_email_account(app):
    existing = make_user("known@test.iq")
    user = google_auth.login_or_register(_profile(email="known@test.iq", sub="google-999"))
    assert user.id == existing.id
    assert user.google_id == "google-999"


def test_google_rejects_unverified_email(app):
    try:
        google_auth.login_or_register(_profile(email_verified=False))
    except google_auth.GoogleAuthError as exc:
        assert "غير موثّق" in exc.message
    else:  # pragma: no cover
        raise AssertionError("unverified email must be rejected")


def test_google_rejects_deactivated_account(app):
    make_user("off@test.iq", active=False)
    try:
        google_auth.login_or_register(_profile(email="off@test.iq"))
    except google_auth.GoogleAuthError as exc:
        assert "معطّل" in exc.message
    else:  # pragma: no cover
        raise AssertionError("deactivated account must be rejected")
