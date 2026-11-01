from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, session
)
from sqlalchemy import or_

from models import db
from models.user import User
from services.security import verify_password
from extensions import limiter

account = Blueprint("account", __name__)


@account.route("/connexion", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def connexion():
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter(
            or_(
                User.email == identifier.lower(),
                User.username == identifier
            )
        ).first()

        if not user or not verify_password(
            password, user.password_hash
        ):
            flash("Identifiants incorrects.")
            return redirect(url_for("account.connexion"))

        if not user.is_active or user.account_status != "active":
            flash(
                "Ton compte n'est pas encore activé. "
                "Vérifie les validations nécessaires."
            )
            return redirect(url_for("account.connexion"))

        session.clear()
        session["user_id"] = user.id
        session.permanent = True

        return redirect(url_for("account.mon_espace"))

    return render_template("connexion.html")


@account.route("/mon-espace")
def mon_espace():
    user_id = session.get("user_id")

    if not user_id:
        flash("Connecte-toi pour accéder à ton espace.")
        return redirect(url_for("account.connexion"))

    user = db.session.get(User, user_id)

    if not user or not user.is_active:
        session.clear()
        flash("Session expirée. Connecte-toi à nouveau.")
        return redirect(url_for("account.connexion"))

    return render_template("espace.html", user=user)


@account.route("/deconnexion", methods=["POST"])
def deconnexion():
    session.clear()
    flash("Tu as été déconnecté.")
    return redirect(url_for("account.connexion"))
