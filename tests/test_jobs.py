from app.extensions import db
from app.models import Application, Job, SavedJob
from app.models.enums import JobStatus
from tests.conftest import login, make_company, make_job, make_user


def test_employer_can_create_company(app, client):
    make_user("boss@test.iq", "employer")
    login(client, "boss@test.iq")
    response = client.post(
        "/employer/company",
        data={"name": "شركة النخيل", "city": "بغداد", "industry": "تقنية المعلومات"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    from app.models import Company

    assert db.session.scalar(db.select(Company).filter_by(name="شركة النخيل")) is not None


def test_verified_employer_can_publish_job(app, client):
    employer = make_user("hire@test.iq", "employer")
    make_company(employer)
    login(client, "hire@test.iq")

    response = client.post(
        "/employer/jobs/new",
        data={
            "title": "مهندس شبكات",
            "description": "وصف كامل للوظيفة يتجاوز ثلاثين حرفًا بسهولة.",
            "city": "البصرة",
            "job_type": "full_time",
            "salary_min": "1500000",
            "salary_max": "2500000",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    job = db.session.scalar(db.select(Job).filter_by(title="مهندس شبكات"))
    assert job is not None
    assert job.status == JobStatus.PUBLISHED.value


def test_unverified_employer_gets_draft(app, client):
    employer = make_user("new@test.iq", "employer")
    make_company(employer, verified=False)
    login(client, "new@test.iq")

    client.post(
        "/employer/jobs/new",
        data={"title": "وظيفة مسودة", "description": "وصف كامل للوظيفة يتجاوز ثلاثين حرفًا."},
        follow_redirects=True,
    )
    job = db.session.scalar(db.select(Job).filter_by(title="وظيفة مسودة"))
    assert job.status == JobStatus.DRAFT.value


def test_seeker_can_apply_once(app, client):
    employer = make_user("emp@test.iq", "employer")
    company = make_company(employer)
    job = make_job(company)

    make_user("seeker@test.iq", "seeker")
    login(client, "seeker@test.iq")

    first = client.post(f"/jobs/{job.id}/apply", data={"slug": job.slug}, follow_redirects=True)
    assert first.status_code == 200
    assert db.session.scalar(db.select(Application).filter_by(job_id=job.id)) is not None

    second = client.post(f"/jobs/{job.id}/apply", data={"slug": job.slug}, follow_redirects=True)
    assert "مسبقًا".encode() in second.data
    assert len(db.session.scalars(db.select(Application).filter_by(job_id=job.id)).all()) == 1


def test_employer_cannot_apply(app, client):
    employer = make_user("emp2@test.iq", "employer")
    company = make_company(employer)
    job = make_job(company)
    login(client, "emp2@test.iq")
    client.post(f"/jobs/{job.id}/apply", data={"slug": job.slug}, follow_redirects=True)
    assert db.session.scalar(db.select(Application).filter_by(job_id=job.id)) is None


def test_save_toggle(app, client):
    employer = make_user("emp3@test.iq", "employer")
    company = make_company(employer)
    job = make_job(company)
    make_user("saver@test.iq", "seeker")
    login(client, "saver@test.iq")

    client.post(f"/api/jobs/{job.id}/save")
    assert db.session.scalar(db.select(SavedJob).filter_by(job_id=job.id)) is not None

    client.post(f"/api/jobs/{job.id}/save")
    assert db.session.scalar(db.select(SavedJob).filter_by(job_id=job.id)) is None


def test_employer_sees_applicant_profile(app, client):
    employer = make_user("emp4@test.iq", "employer")
    company = make_company(employer)
    job = make_job(company)

    seeker = make_user("applicant@test.iq", "seeker")
    seeker.full_name = "زينب كريم"
    db.session.commit()

    login(client, "applicant@test.iq")
    client.post(f"/jobs/{job.id}/apply", data={"slug": job.slug}, follow_redirects=True)
    client.post("/logout")

    login(client, "emp4@test.iq")
    response = client.get("/employer/applicants")
    assert response.status_code == 200
    assert "زينب كريم".encode() in response.data


def test_status_update_notifies_seeker(app, client):
    from app.models import Notification

    employer = make_user("emp5@test.iq", "employer")
    company = make_company(employer)
    job = make_job(company)

    seeker = make_user("notifyme@test.iq", "seeker")
    login(client, "notifyme@test.iq")
    client.post(f"/jobs/{job.id}/apply", data={"slug": job.slug}, follow_redirects=True)
    client.post("/logout")

    app_row = db.session.scalar(db.select(Application).filter_by(job_id=job.id))
    login(client, "emp5@test.iq")
    client.post(f"/employer/applications/{app_row.id}/status", data={"status": "shortlisted"})

    db.session.refresh(app_row)
    assert app_row.status == "shortlisted"
    assert db.session.scalar(db.select(Notification).filter_by(user_id=seeker.id)) is not None
