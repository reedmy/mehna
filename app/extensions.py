"""Flask extension instances.

They are created unbound here and initialised in the app factory, which keeps
models/services importable without an application context.
"""

from __future__ import annotations

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)

login_manager.login_view = "auth.login"
login_manager.login_message = "سجّل الدخول للمتابعة."
login_manager.login_message_category = "info"
login_manager.session_protection = "strong"


@login_manager.user_loader
def _load_user(user_id: str):
    from app.models import User

    return db.session.get(User, user_id)
