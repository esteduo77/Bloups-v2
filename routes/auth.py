from datetime import date, datetime, timezone

from flask import (
    Blueprint,
    current_app,
    render_template,
    request,
    redirect,
    url_for,
    flash
)

from email_validator import validate_email, EmailNotValidError

from models import db
from models.user import User
from services.security import hash_password, create_token, verify_token
from services.email import send_email


auth = Blueprint("auth", __name__)


def calculate_age(birth_date):
    today = date.today()

    return (
        today.year - birth_date.year
        - ((today.month, today.day) <
           (birth_date.month, birth_date.day))
    )


def activate_if_ready(user):
    age = calculate_age(user.birth_date)

    email_ok = user.email_verified_at is not None

    parent_ok = (
        age >= 15 or user.guardian_consent_at is not None
    )

    if email_ok and parent_ok:
        user.account_status = "active"
        user.is_active = True
    else:
        user.is_active = False


def send_validation_email(user):
    token = create_token(
        current_app.config["SECRET_KEY"],
        "email_verification",
        user.id
    )

    link = url_for(
        "auth.verifier_email",
        token=token,
        _external=True
    )

    send_email(
        user.email,
        "Vérification de ton adresse e-mail — BLOOPS",
        f"Pour vérifier ton adresse e-mail, ouvre ce lien :\n\n{link}\n\n"
        "Ce lien expire après une heure."
    )


def send_parent_request(user):
    token = create_token(
        current_app.config["SECRET_KEY"],
        "parent_consent",
        user.id
    )

    link = url_for(
        "auth.consentement_parent",
        token=token,
        _external=True
    )

    send_email(
        user.guardian_email,
        "Demande de consentement parental — BLOOPS",
        (
            f"Une demande de création de compte BLOOPS a été effectuée "
            f"pour le pseudo {user.username}.\n\n"
            f"Pour consulter et accepter cette demande :\n{link}\n\n"
            "Ce lien expire après 48 heures."
        )
    )


@auth.route("/inscription", methods=["GET", "POST"])
def inscription():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        birth_date_text = request.form.get("birth_date", "")
        guardian_email = request.form.get(
            "guardian_email", ""
        ).strip().lower()

        if not 3 <= len(username) <= 30:
            flash("Le pseudo doit contenir entre 3 et 30 caractères.")
            return redirect(url_for("auth.inscription"))

        try:
            email = validate_email(email).normalized
        except EmailNotValidError:
            flash("Adresse e-mail invalide.")
            return redirect(url_for("auth.inscription"))

        if len(password) < 12:
            flash("Le mot de passe doit contenir au moins 12 caractères.")
            return redirect(url_for("auth.inscription"))

        try:
            birth_date = date.fromisoformat(birth_date_text)
        except (ValueError, TypeError):
            flash("Date de naissance invalide.")
            return redirect(url_for("auth.inscription"))

        if birth_date >= date.today():
            flash("Date de naissance invalide.")
            return redirect(url_for("auth.inscription"))

        age = calculate_age(birth_date)

        if User.query.filter_by(username=username).first():
            flash("Ce pseudo est déjà utilisé.")
            return redirect(url_for("auth.inscription"))

        if User.query.filter_by(email=email).first():
            flash("Cette adresse e-mail est déjà utilisée.")
            return redirect(url_for("auth.inscription"))

        if age < 15:
            if not guardian_email:
                flash("L'adresse e-mail du représentant légal est nécessaire.")
                return redirect(url_for("auth.inscription"))

            try:
                guardian_email = validate_email(
                    guardian_email
                ).normalized
            except EmailNotValidError:
                flash("Adresse e-mail du représentant légal invalide.")
                return redirect(url_for("auth.inscription"))

            if guardian_email == email:
                flash("Le représentant légal doit utiliser une autre adresse.")
                return redirect(url_for("auth.inscription"))

            status = "pending_parent"

        else:
            guardian_email = None
            status = "pending_email"

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            birth_date=birth_date,
            guardian_email=guardian_email,
            account_status=status,
            is_active=False
        )

        db.session.add(user)
        db.session.commit()

        try:
            # Tous les utilisateurs doivent vérifier leur adresse e-mail.
            send_validation_email(user)

            if age < 15:
                # Les moins de 15 ans doivent aussi obtenir
                # le consentement de leur représentant légal.
                send_parent_request(user)

                flash(
                    "Deux e-mails ont été envoyés : "
                    "un pour vérifier ton adresse et un pour "
                    "demander le consentement de ton représentant légal."
                )
            else:
                flash(
                    "Un e-mail de vérification vient d'être envoyé."
                )

        except Exception:
            current_app.logger.exception(
                "Échec de l'envoi d'un e-mail d'inscription."
            )

            flash(
                "Le compte est en attente. "
                "Au moins un e-mail n'a pas pu être envoyé."
            )

        return redirect(url_for("auth.inscription"))

    return render_template("inscription.html")


@auth.route("/verifier-email/<token>", methods=["GET", "POST"])
def verifier_email(token):

    user_id = verify_token(
        current_app.config["SECRET_KEY"],
        token,
        "email_verification",
        max_age=3600
    )

    if not user_id:
        flash("Le lien est invalide ou expiré.")
        return redirect(url_for("auth.inscription"))

    user = db.session.get(User, user_id)

    if not user:
        flash("Compte introuvable.")
        return redirect(url_for("auth.inscription"))

    if request.method == "POST":

        if user.email_verified_at is None:
            user.email_verified_at = datetime.now(timezone.utc)

        activate_if_ready(user)
        db.session.commit()

        flash("Adresse e-mail vérifiée.")
        return redirect(url_for("auth.inscription"))

    return render_template("verifier_email.html")


@auth.route("/consentement-parent/<token>", methods=["GET", "POST"])
def consentement_parent(token):

    user_id = verify_token(
        current_app.config["SECRET_KEY"],
        token,
        "parent_consent",
        max_age=172800
    )

    if not user_id:
        flash("Le lien est invalide ou expiré.")
        return redirect(url_for("auth.inscription"))

    user = db.session.get(User, user_id)

    if not user:
        flash("Demande introuvable.")
        return redirect(url_for("auth.inscription"))

    if calculate_age(user.birth_date) >= 15:
        flash("Cette demande ne nécessite pas de consentement parental.")
        return redirect(url_for("auth.inscription"))

    if request.method == "POST":

        if user.guardian_consent_at is None:
            user.guardian_consent_at = datetime.now(timezone.utc)

        activate_if_ready(user)
        db.session.commit()

        flash("La demande de consentement a été enregistrée.")
        return redirect(url_for("auth.inscription"))

    return render_template("consentement_parent.html")
