from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

login_manager.login_view = "auth.login"
login_manager.login_message = (
    "Please log in to make changes."
)
login_manager.login_message_category = "error"
login_manager.session_protection = "strong"


def create_app():
    app = Flask(
        __name__,
        instance_relative_config=True,
        static_url_path="/recipe-static",
    )

    app.config.from_pyfile("config.py")

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
