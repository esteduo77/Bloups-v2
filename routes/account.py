import re

from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, session
)
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from models import db
from models.user import User
from services.security import verify_password, hash_password
from extensions import limiter


account = Blueprint("account", __name__)


def get_current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    user = db.session.get(User, user_id)

    if not user or not user.is_active:
        session.clear()
        return None

    return user


@account.route("/connexion", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def connexion():
    if request.method == "POST":
        identifier = request.form.get(
            "identifier", ""
        ).strip()

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
            flash("Identifiants incorrects.", "error")
            return redirect(url_for("account.connexion"))

        if not user.is_active or user.account_status != "active":
            flash(
                "Ton compte n'est pas encore activé.",
                "error"
            )
            return redirect(url_for("account.connexion"))

        session.clear()
        session["user_id"] = user.id
        session.permanent = True

        return redirect(url_for("account.mon_espace"))

    return render_template("connexion.html")


@account.route("/mon-espace")
def mon_espace():
    user = get_current_user()

    if not user:
        flash("Connecte-toi pour accéder à ton espace.", "error")
        return redirect(url_for("account.connexion"))

    return render_template("espace.html", user=user)


@account.route("/profil", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def profil():
    user = get_current_user()

    if not user:
        flash("Connecte-toi pour accéder à ton profil.", "error")
        return redirect(url_for("account.connexion"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        bio = request.form.get("bio", "").strip()
        visibility = request.form.get(
            "profile_visibility", "private"
        )

        if not re.fullmatch(r"[A-Za-z0-9_-]{3,30}", username):
            flash(
                "Le pseudonyme doit contenir 3 à 30 caractères "
                "parmi les lettres, chiffres, _ et -.",
                "error"
            )
            return redirect(url_for("account.profil"))

        if len(bio) > 300:
            flash("La description est trop longue.", "error")
            return redirect(url_for("account.profil"))

        if visibility not in ("private", "public"):
            flash("Choix de confidentialité invalide.", "error")
            return redirect(url_for("account.profil"))

        existing_user = User.query.filter(
            User.username == username,
            User.id != user.id
        ).first()

        if existing_user:
            flash("Ce pseudonyme est déjà utilisé.", "error")
            return redirect(url_for("account.profil"))

        user.username = username
        user.bio = bio
        user.profile_visibility = visibility

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Ce pseudonyme est déjà utilisé.", "error")
            return redirect(url_for("account.profil"))

        flash("Ton profil a été mis à jour.", "success")
        return redirect(url_for("account.profil"))

    return render_template("profil.html", user=user)


@account.route("/parametres", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def parametres():
    user = get_current_user()

    if not user:
        flash("Connecte-toi pour accéder aux paramètres.", "error")
        return redirect(url_for("account.connexion"))

    if request.method == "POST":
        old_password = request.form.get("old_password", "")
        new_password = request.form.get("new_password", "")
        confirmation = request.form.get("confirmation", "")

        if not verify_password(old_password, user.password_hash):
            flash("Ancien mot de passe incorrect.", "error")
            return redirect(url_for("account.parametres"))

        if len(new_password) < 12:
            flash(
                "Le nouveau mot de passe doit contenir "
                "au moins 12 caractères.",
                "error"
            )
            return redirect(url_for("account.parametres"))

        if new_password != confirmation:
            flash("Les mots de passe ne correspondent pas.", "error")
            return redirect(url_for("account.parametres"))

        if new_password == old_password:
            flash(
                "Choisis un mot de passe différent de l'ancien.",
                "error"
            )
            return redirect(url_for("account.parametres"))

        user.password_hash = hash_password(new_password)
        db.session.commit()

        session.clear()

        flash(
            "Mot de passe modifié. Connecte-toi à nouveau.",
            "success"
        )
        return redirect(url_for("account.connexion"))

    return render_template("parametres.html", user=user)


@account.route("/deconnexion", methods=["POST"])
def deconnexion():
    session.clear()
    flash("Tu as été déconnecté.", "success")
    return redirect(url_for("account.connexion"))
