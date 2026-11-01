import os
from datetime import timedelta

from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect

from models import db
from extensions import limiter

csrf = CSRFProtect()


def create_app(test_config=None):
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ.get(
        "BLOOPS_SECRET_KEY"
    )

    if not app.config["SECRET_KEY"]:
        raise RuntimeError(
            "La variable BLOOPS_SECRET_KEY doit être configurée."
        )

    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "BLOOPS_DATABASE_URL",
        "sqlite:///bloups.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = (
        os.environ.get("BLOOPS_COOKIE_SECURE", "0") == "1"
    )
    app.config["RATELIMIT_STORAGE_URI"] = os.environ.get(
        "BLOOPS_RATE_LIMIT_STORAGE_URI",
        "memory://"
    )

    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    from models.user import User
    from routes.auth import auth
    from routes.account import account

    app.register_blueprint(auth)
    app.register_blueprint(account)

    with app.app_context():
        db.create_all()

    @app.route("/")
    def accueil():
        return render_template("accueil.html")

    @app.errorhandler(404)
    def page_introuvable(error):
        return render_template("erreurs/404.html"), 404

    @app.errorhandler(500)
    def erreur_interne(error):
        return render_template("erreurs/500.html"), 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )
