from tests.conftest import make_company, make_job, make_user


def test_home_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "مهنة".encode() in response.data


def test_jobs_page_loads(client):
    assert client.get("/jobs").status_code == 200


def test_jobs_page_with_filters(client):
    assert client.get("/jobs?q=محاسب&city=بغداد&job_type=full_time").status_code == 200


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_404(client):
    assert client.get("/no-such-page").status_code == 404


def test_pricing_and_about(client):
    assert client.get("/pricing").status_code == 200
    assert client.get("/about").status_code == 200
    assert client.get("/how-it-works").status_code == 200


def test_search_normalises_arabic(app, client):
    employer = make_user("emp@test.iq", "employer")
    company = make_company(employer)
    make_job(company, title="سائق توصيل")

    # "سواق" is Iraqi colloquial for "سائق" — the synonym table must expand it.
    response = client.get("/jobs?q=سواق")
    assert response.status_code == 200
    assert "سائق توصيل".encode() in response.data


def test_job_detail_shows_company(app, client):
    employer = make_user("emp2@test.iq", "employer")
    company = make_company(employer, name="شركة الرافدين")
    job = make_job(company)

    response = client.get(f"/jobs/{job.id}/{job.slug}")
    assert response.status_code == 200
    assert "شركة الرافدين".encode() in response.data
