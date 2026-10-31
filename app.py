import os

from flask import Flask, render_template


def create_app():
    app = Flask(__name__)

    # Configuration de sécurité : la clé sera fournie par l'environnement.
    app.config["SECRET_KEY"] = os.environ.get("BLOOPS_SECRET_KEY")

    if not app.config["SECRET_KEY"]:
        raise RuntimeError(
            "La variable BLOOPS_SECRET_KEY doit être configurée."
        )

    # Page d'accueil
    @app.route("/")
    def accueil():
        return render_template("accueil.html")

    # Page introuvable
    @app.errorhandler(404)
    def page_introuvable(error):
        return render_template("erreurs/404.html"), 404

    # Erreur interne
    @app.errorhandler(500)
    def erreur_interne(error):
        return render_template("erreurs/500.html"), 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
