from app.extensions import db
from app.models import Company
from tests.conftest import login, make_company, make_job, make_user


def test_employer_cannot_edit_another_company(app, client):
    owner = make_user("owner@test.iq", "employer")
    company = make_company(owner, name="شركة أصلية")

    make_user("intruder@test.iq", "employer")
    login(client, "intruder@test.iq")

    response = client.post(
        "/employer/company",
        data={"name": "اسم مسروق"},
        follow_redirects=True,
    )
    # The intruder has no company → this creates a new one, it must not touch the existing one.
    assert response.status_code == 200
    db.session.expire_all()
    original = db.session.get(Company, company.id)
    assert original.name == "شركة أصلية"


def test_employer_cannot_publish_another_employers_job(app, client):
    owner = make_user("owner2@test.iq", "employer")
    company = make_company(owner)
    job = make_job(company)

    make_user("thief@test.iq", "employer")
    login(client, "thief@test.iq")

    response = client.post(f"/employer/jobs/{job.id}/publish", follow_redirects=False)
    assert response.status_code == 302
    db.session.refresh(job)
    assert job.status == "published"  # unchanged — the thief could not publish or alter it


def test_seeker_cannot_open_employer_area(app, client):
    make_user("seeker2@test.iq", "seeker")
    login(client, "seeker2@test.iq")
    response = client.get("/employer/", follow_redirects=False)
    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]


def test_non_admin_cannot_open_admin(app, client):
    make_user("seeker3@test.iq", "seeker")
    login(client, "seeker3@test.iq")
    assert client.get("/admin/").status_code == 403


def test_admin_can_verify_company(app, client):
    admin = make_user("admin2@test.iq", "admin")
    owner = make_user("owner3@test.iq", "employer")
    company = make_company(owner, verified=False)

    login(client, admin.email)
    response = client.post(f"/admin/companies/{company.id}/verify", follow_redirects=True)
    assert response.status_code == 200

    db.session.refresh(company)
    assert company.verification_status == "verified"
    assert company.verified_by_id == admin.id


def test_admin_cannot_deactivate_self(app, client):
    admin = make_user("admin3@test.iq", "admin")
    login(client, admin.email)
    client.post(f"/admin/users/{admin.id}/toggle", follow_redirects=True)
    db.session.refresh(admin)
    assert admin.is_active is True


def test_employer_cannot_update_status_of_foreign_application(app, client):
    from app.extensions import db
    from app.models import Application

    owner = make_user("owner4@test.iq", "employer")
    company = make_company(owner)
    job = make_job(company)

    seeker = make_user("applicant2@test.iq", "seeker")
    login(client, seeker.email)
    client.post(f"/jobs/{job.id}/apply", data={"slug": job.slug}, follow_redirects=True)
    client.post("/logout")

    app_row = db.session.scalar(db.select(Application).filter_by(job_id=job.id))

    make_user("outsider@test.iq", "employer")
    login(client, "outsider@test.iq")
    response = client.post(
        f"/employer/applications/{app_row.id}/status", data={"status": "accepted"}
    )
    assert response.status_code == 302
    db.session.refresh(app_row)
    assert app_row.status == "submitted"  # the outsider could not change it
