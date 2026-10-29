from flask import Flask
from dotenv import load_dotenv

load_dotenv()  # must run before Config is imported, since Config reads os.environ at import time

from app.config import Config
from app.extensions import db, migrate, jwt, cors
from app.routes import register_blueprints


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app)  # default: allow all origins — tighten this before deploying

    # Models must be imported (even if unused directly here) so that
    # Flask-Migrate can detect them when generating migrations.
    from app import models  # noqa: F401

    register_blueprints(app)

    from app.cli import jobs_cli  # `flask jobs ...`
    app.cli.add_command(jobs_cli)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}, 200

    return app
