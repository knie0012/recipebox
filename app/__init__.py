from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone



db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

login_manager.login_view = "auth.login"
login_manager.login_message = (
    "Please log in to make changes."
)
login_manager.login_message_category = "error"
login_manager.session_protection = "strong"


def format_timeago(value):
    if value is None:
        return ""

    now = datetime.now()

    difference = now - value
    seconds = max(0, int(difference.total_seconds()))

    if seconds < 60:
        return "just now"

    minutes = seconds // 60

    if minutes < 60:
        return (
            f"{minutes} minute ago"
            if minutes == 1
            else f"{minutes} minutes ago"
        )

    hours = minutes // 60

    if hours < 24:
        return (
            f"{hours} hour ago"
            if hours == 1
            else f"{hours} hours ago"
        )

    days = hours // 24

    if days == 1:
        return "yesterday"

    if days < 7:
        return f"{days} days ago"

    weeks = days // 7

    if weeks < 5:
        return (
            f"{weeks} week ago"
            if weeks == 1
            else f"{weeks} weeks ago"
        )

    months = days // 30

    if months < 12:
        return (
            f"{months} month ago"
            if months == 1
            else f"{months} months ago"
        )

    years = days // 365

    return (
        f"{years} year ago"
        if years == 1
        else f"{years} years ago"
    )
    

def create_app():
    app = Flask(
        __name__,
        instance_relative_config=True,
        static_url_path="/recipe-static",
    )

    app.config.from_pyfile("config.py")
    app.jinja_env.filters["timeago"] = format_timeago
    
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from app.models import Users

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(
                Users,
                int(user_id),
            )
        except (TypeError, ValueError):
            return None

    from app.auth import auth
    from app.imports import imports
    from app.main import main
    from app.recipes import recipes

    app.register_blueprint(auth)
    app.register_blueprint(imports)
    app.register_blueprint(main)
    app.register_blueprint(recipes)

    return app
