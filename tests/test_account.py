"""Account control: signed-in switcher, switching, settings, progressive apply."""

from __future__ import annotations

from app.extensions import db
from app.models import Application, User
from tests.conftest import login, make_company, make_job, make_user


def test_login_page_shows_account_switcher_when_signed_in(app, client):
    make_user("me@test.iq")
    login(client, "me@test.iq")

    response = client.get("/login")
    assert response.status_code == 200
    assert "أنت مسجل الدخول".encode() in response.data
    assert "تبديل الحساب".encode() in response.data
    assert b"/auth/switch" in response.data


def test_switch_account_logs_out(app, client):
    make_user("me@test.iq")
    login(client, "me@test.iq")

    response = client.post("/auth/switch", follow_redirects=False)
    assert response.status_code == 302
    # Switching sends the visitor to the Google chooser (configured in tests).
    assert response.headers["Location"] == "/auth/google"
    assert client.get("/dashboard/").status_code == 302

    chooser = client.get("/auth/google", follow_redirects=False)
    assert chooser.status_code == 302
    assert "accounts.google.com" in chooser.headers["Location"]


def test_account_page_is_available_for_every_role(app, client):
    for role in ("seeker", "employer", "admin"):
        email = f"{role}-settings@test.iq"
        make_user(email, role)
        login(client, email)
        response = client.get("/account")
        assert response.status_code == 200
        assert "إعدادات الحساب".encode() in response.data
        client.post("/logout")


def test_account_updates_name_and_phone(app, client):
    user = make_user("edit@test.iq")
    login(client, "edit@test.iq")

    response = client.post(
        "/account",
        data={"full_name": "علي حسن", "phone": "07701234567"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    db.session.expire_all()
    fresh = db.session.get(User, user.id)
    assert fresh.full_name == "علي حسن"
    assert fresh.phone == "+9647701234567"


def test_quick_apply_asks_for_phone_once(app, client):
    employer = make_user("emp@test.iq", "employer")
    job = make_job(make_company(employer))
    make_user("nophone@test.iq", phone=None)
    login(client, "nophone@test.iq")

    response = client.post(f"/jobs/{job.id}/apply", data={"slug": job.slug}, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].startswith(f"/jobs/{job.id}/")
    assert response.headers["Location"].endswith("/apply")

    page = client.get(f"/jobs/{job.id}/{job.slug}/apply")
    assert page.status_code == 200
    assert "رقم الهاتف".encode() in page.data

    submit = client.post(
        f"/jobs/{job.id}/{job.slug}/apply",
        data={
            "full_name": "نورة",
            "phone": "07701234567",
            "city": "بغداد",
            "save_to_profile": "1",
            "cover_letter": "جاهزة للعمل",
        },
        follow_redirects=True,
    )
    assert submit.status_code == 200

    application = db.session.scalar(db.select(Application).filter_by(job_id=job.id))
    assert application is not None
    assert application.seeker.phone == "+9647701234567"
    assert application.seeker.profile.city == "بغداد"


def test_apply_form_rejects_missing_phone(app, client):
    employer = make_user("emp2@test.iq", "employer")
    job = make_job(make_company(employer))
    make_user("nophone2@test.iq", phone=None)
    login(client, "nophone2@test.iq")

    response = client.post(
        f"/jobs/{job.id}/{job.slug}/apply",
        data={"full_name": "نورة", "phone": ""},
    )
    assert response.status_code == 422
    assert db.session.scalar(db.select(Application).filter_by(job_id=job.id)) is None


def test_apply_form_is_prefilled_from_profile(app, client):
    employer = make_user("emp3@test.iq", "employer")
    job = make_job(make_company(employer))
    user = make_user("filled@test.iq")
    user.profile.city = "أربيل"
    user.profile.cv_url = "https://example.com/cv.pdf"
    db.session.commit()
    login(client, "filled@test.iq")

    response = client.get(f"/jobs/{job.id}/{job.slug}/apply")
    assert response.status_code == 200
    assert "أربيل".encode() in response.data
    assert b"https://example.com/cv.pdf" in response.data
