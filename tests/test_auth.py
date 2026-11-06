from app.extensions import db
from app.models import User
from tests.conftest import login, make_user


def test_register_creates_user_and_profile(app, client):
    response = client.post(
        "/register",
        data={
            "full_name": "علي حسين",
            "email": "new@test.iq",
            "password": "Passw0rd!",
            "phone": "07701234567",
            "role": "seeker",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    user = db.session.scalar(db.select(User).filter_by(email="new@test.iq"))
    assert user is not None
    assert user.profile is not None
    assert user.phone == "+9647701234567"


def test_register_rejects_duplicate_email(app, client):
    make_user("dup@test.iq")
    response = client.post(
        "/register",
        data={"full_name": "شخص آخر", "email": "dup@test.iq", "password": "Passw0rd!"},
    )
    assert response.status_code == 422
    assert "مسجّل مسبقًا".encode() in response.data


def test_register_rejects_weak_password(app, client):
    response = client.post(
        "/register",
        data={"full_name": "مستخدم", "email": "weak@test.iq", "password": "123"},
    )
    assert response.status_code == 422


def test_login_success(client, users):
    response = login(client, "seeker@test.iq")
    assert response.status_code == 200
    assert "أهلًا".encode() in response.data


def test_login_wrong_password(client, users):
    response = client.post("/login", data={"email": "seeker@test.iq", "password": "wrong"})
    assert response.status_code == 401


def test_login_page_lists_quick_access(client, users):
    response = client.get("/login")
    assert response.status_code == 200
    assert "جرب منصة مهنة بسرعة".encode() in response.data


def test_login_demo_unknown_account(client, users):
    response = client.post("/login/demo/does-not-exist", follow_redirects=True)
    assert response.status_code == 200
    assert b"/login" in response.data


def test_login_demo_account_enters_dashboard(client, users):
    response = client.post("/login/demo/seeker", follow_redirects=True)
    assert response.status_code == 200
    assert client.get("/dashboard/").status_code == 200


def test_deactivated_user_cannot_login(app, client):
    make_user("blocked@test.iq", active=False)
    response = client.post("/login", data={"email": "blocked@test.iq", "password": "Passw0rd!"})
    assert response.status_code == 401


def test_logout_requires_post(app, client, users):
    login(client, "seeker@test.iq")
    assert client.get("/logout").status_code == 405
    assert client.post("/logout", follow_redirects=True).status_code == 200


def test_dashboard_requires_login(client):
    response = client.get("/dashboard/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
