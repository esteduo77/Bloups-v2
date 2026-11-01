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
from sqlalchemy.exc import IntegrityError

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

    if age >= 15:
        parent_ok = True
    else:
        parent_ok = (
            user.guardian_consent_1_at is not None
            and user.guardian_consent_2_at is not None
        )

    if email_ok and parent_ok:
        user.account_status = "active"
        user.is_active = True
    else:
        user.account_status = (
            "pending_parent" if age < 15 else "pending_email"
        )
        user.is_active = False


def send_validation_email(user):
    token = create_token(
        current_app.config["SECRET_KEY"],
        "email_verification",
        user.id
    )
    link = url_for(
        "auth.verifier_email", token=token, _external=True
    )
    send_email(
        user.email,
        "Vérification de ton adresse e-mail — BLOOPS",
        (
            "Pour vérifier ton adresse e-mail, ouvre ce lien :\n\n"
            f"{link}\n\nCe lien expire après une heure."
        )
    )


def send_parent_request(user, guardian_number):
    guardian_email = (
        user.guardian_email
        if guardian_number == 1
        else user.guardian_email_2
    )
    purpose = f"parent_consent_{guardian_number}"
    token = create_token(
        current_app.config["SECRET_KEY"], purpose, user.id
    )
    link = url_for(
        "auth.consentement_parent",
        guardian_number=guardian_number,
        token=token,
        _external=True
    )
    send_email(
        guardian_email,
        "Consentement parental — BLOOPS",
        (
            f"Une demande de création de compte a été effectuée "
            f"pour le pseudo {user.username}.\n\n"
            f"Vous êtes le représentant légal numéro {guardian_number}.\n\n"
            f"Pour consulter la demande :\n{link}\n\n"
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
        guardian_email_2 = request.form.get(
            "guardian_email_2", ""
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
            if not guardian_email or not guardian_email_2:
                flash(
                    "Les deux adresses des représentants légaux sont obligatoires."
                )
                return redirect(url_for("auth.inscription"))

            try:
                guardian_email = validate_email(
                    guardian_email
                ).normalized
                guardian_email_2 = validate_email(
                    guardian_email_2
                ).normalized
            except EmailNotValidError:
                flash("Une adresse parentale est invalide.")
                return redirect(url_for("auth.inscription"))

            if len({email, guardian_email, guardian_email_2}) != 3:
                flash(
                    "Les deux représentants légaux doivent avoir "
                    "des adresses distinctes de celle de l'utilisateur."
                )
                return redirect(url_for("auth.inscription"))

            status = "pending_parent"
        else:
            guardian_email = None
            guardian_email_2 = None
            status = "pending_email"

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            birth_date=birth_date,
            guardian_email=guardian_email,
            guardian_email_2=guardian_email_2,
            account_status=status,
            is_active=False
        )

        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Ce pseudo ou cette adresse e-mail est déjà utilisé.")
            return redirect(url_for("auth.inscription"))

        try:
            send_validation_email(user)
            if age < 15:
                send_parent_request(user, 1)
                send_parent_request(user, 2)
                flash(
                    "Les e-mails de vérification et les deux demandes "
                    "parentales ont été envoyés."
                )
            else:
                flash("Un e-mail de vérification vient d'être envoyé.")
        except Exception:
            current_app.logger.exception(
                "Échec de l'envoi d'un e-mail d'inscription."
            )
            flash(
                "Le compte est en attente. Au moins un e-mail n'a pas "
                "pu être envoyé ; une procédure de renvoi sera nécessaire."
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


@auth.route(
    "/consentement-parent/<int:guardian_number>/<token>",
    methods=["GET", "POST"]
)
def consentement_parent(guardian_number, token):
    if guardian_number not in (1, 2):
        return "Numéro de représentant légal invalide.", 400

    purpose = f"parent_consent_{guardian_number}"
    user_id = verify_token(
        current_app.config["SECRET_KEY"],
        token,
        purpose,
        max_age=172800
    )

    if not user_id:
        return "Lien invalide ou expiré.", 400

    user = db.session.get(User, user_id)
    if not user:
        return "Compte introuvable.", 404

    if calculate_age(user.birth_date) >= 15:
        return "Ce compte ne nécessite pas de consentement parental.", 400

    consent_field = (
        "guardian_consent_1_at"
        if guardian_number == 1
        else "guardian_consent_2_at"
    )

    if getattr(user, consent_field) is not None:
        return "Cette autorisation a déjà été enregistrée.", 409

    if request.method == "POST":
        decision = request.form.get("decision")
        if decision != "approved":
            return "Décision invalide.", 400

        setattr(user, consent_field, datetime.now(timezone.utc))
        activate_if_ready(user)
        db.session.commit()

        return render_template(
            "consentement_parent.html",
            completed=True,
            activated=user.is_active,
            guardian_number=guardian_number
        )

    return render_template(
        "consentement_parent.html",
        completed=False,
        guardian_number=guardian_number
    )
