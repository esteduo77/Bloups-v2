from datetime import date, datetime, timezone

from sqlalchemy import or_

from models import db
from models.contact import Contact
from models.contact_request import ContactRequest
from models.parental_approval import ParentalApproval
from models.user import User
from models.user_block import UserBlock


def calculate_age(birth_date):
    today = date.today()
    return (
        today.year - birth_date.year
        - ((today.month, today.day) <
           (birth_date.month, birth_date.day))
    )


def get_contact_pair(user_id, contact_user_id):
    return min(user_id, contact_user_id), max(user_id, contact_user_id)


def are_contacts(user_id, contact_user_id):
    first_id, second_id = get_contact_pair(user_id, contact_user_id)
    return Contact.query.filter_by(
        user_id=first_id,
        contact_user_id=second_id
    ).first() is not None


def is_blocked_between(user_id, other_user_id):
    return UserBlock.query.filter(
        or_(
            (
                (UserBlock.blocker_id == user_id)
                & (UserBlock.blocked_user_id == other_user_id)
            ),
            (
                (UserBlock.blocker_id == other_user_id)
                & (UserBlock.blocked_user_id == user_id)
            )
        )
    ).first() is not None


def block_user(blocker, blocked):
    if blocker.id == blocked.id:
        raise ValueError("Tu ne peux pas te bloquer toi-même.")

    existing = UserBlock.query.filter_by(
        blocker_id=blocker.id,
        blocked_user_id=blocked.id
    ).first()
    if existing:
        raise ValueError("Cet utilisateur est déjà bloqué.")

    now = datetime.now(timezone.utc)
    db.session.add(UserBlock(
        blocker_id=blocker.id,
        blocked_user_id=blocked.id
    ))

    first_id, second_id = get_contact_pair(blocker.id, blocked.id)
    Contact.query.filter_by(
        user_id=first_id,
        contact_user_id=second_id
    ).delete(synchronize_session=False)

    pending_requests = ContactRequest.query.filter(
        or_(
            (
                (ContactRequest.sender_id == blocker.id)
                & (ContactRequest.receiver_id == blocked.id)
            ),
            (
                (ContactRequest.sender_id == blocked.id)
                & (ContactRequest.receiver_id == blocker.id)
            )
        ),
        ContactRequest.status == "pending"
    ).all()

    for contact_request in pending_requests:
        contact_request.status = "cancelled"
        approvals = ParentalApproval.query.filter_by(
            request_id=contact_request.id,
            status="pending"
        ).all()
        for approval in approvals:
            approval.status = "rejected"
            approval.decided_at = now

    db.session.commit()


def unblock_user(blocker, blocked):
    block = UserBlock.query.filter_by(
        blocker_id=blocker.id,
        blocked_user_id=blocked.id
    ).first()
    if not block:
        raise ValueError("Cet utilisateur n'est pas dans ta liste.")

    db.session.delete(block)
    db.session.commit()


def get_blocked_users(user):
    return User.query.join(
        UserBlock,
        UserBlock.blocked_user_id == User.id
    ).filter(
        UserBlock.blocker_id == user.id
    ).order_by(User.username.asc()).all()


def create_contact_request(sender, receiver):
    if sender.id == receiver.id:
        raise ValueError("Tu ne peux pas t'ajouter toi-même.")

    if not sender.is_active or not receiver.is_active:
        raise ValueError("Les deux comptes doivent être actifs.")

    if is_blocked_between(sender.id, receiver.id):
        raise ValueError("Cette demande ne peut pas être envoyée.")

    if are_contacts(sender.id, receiver.id):
        raise ValueError("Cette personne est déjà dans tes contacts.")

    existing = ContactRequest.query.filter(
        or_(
            (
                (ContactRequest.sender_id == sender.id)
                & (ContactRequest.receiver_id == receiver.id)
            ),
            (
                (ContactRequest.sender_id == receiver.id)
                & (ContactRequest.receiver_id == sender.id)
            )
        ),
        ContactRequest.status == "pending"
    ).first()

    if existing:
        raise ValueError("Une demande est déjà en attente.")

    is_under_15 = calculate_age(sender.birth_date) < 15
    guardian_emails = []

    if is_under_15:
        guardian_emails = [
            sender.guardian_email,
            sender.guardian_email_2
        ]
        if not all(guardian_emails):
            raise ValueError(
                "Les deux adresses e-mail des représentants légaux "
                "doivent être enregistrées."
            )
        normalized = [email.strip().lower() for email in guardian_emails]
        if normalized[0] == normalized[1]:
            raise ValueError(
                "Les deux représentants légaux doivent avoir "
                "des adresses e-mail distinctes."
            )

    contact_request = ContactRequest(
        sender_id=sender.id,
        receiver_id=receiver.id,
        status="pending"
    )
    db.session.add(contact_request)
    db.session.flush()

    if is_under_15:
        for number, email in enumerate(guardian_emails, start=1):
            db.session.add(
                ParentalApproval(
                    request_id=contact_request.id,
                    guardian_number=number,
                    guardian_email=email,
                    status="pending"
                )
            )

    db.session.commit()
    return contact_request


def decide_parental_approval(approval, decision):
    if decision not in ("approved", "rejected"):
        raise ValueError("Décision invalide.")
    if approval.status != "pending":
        raise ValueError("Cette autorisation a déjà été traitée.")

    contact_request = db.session.get(ContactRequest, approval.request_id)
    if not contact_request or contact_request.status != "pending":
        raise ValueError("Cette demande n'est plus active.")

    now = datetime.now(timezone.utc)
    approval.status = decision
    approval.decided_at = now

    if decision == "rejected":
        contact_request.status = "rejected"
        for other in ParentalApproval.query.filter_by(
            request_id=contact_request.id,
            status="pending"
        ).all():
            other.status = "rejected"
            other.decided_at = now

    db.session.commit()


def parental_approvals_complete(request_id):
    approvals = ParentalApproval.query.filter_by(
        request_id=request_id
    ).all()
    if not approvals:
        return True
    return (
        len(approvals) == 2
        and all(item.status == "approved" for item in approvals)
    )


def accept_contact_request(contact_request, receiver):
    if contact_request.receiver_id != receiver.id:
        raise PermissionError("Tu ne peux pas accepter cette demande.")
    if contact_request.status != "pending":
        raise ValueError("Cette demande n'est plus en attente.")
    if is_blocked_between(
        contact_request.sender_id, contact_request.receiver_id
    ):
        raise PermissionError("Cette demande ne peut plus être acceptée.")
    if not parental_approvals_complete(contact_request.id):
        raise PermissionError(
            "Les deux représentants légaux doivent approuver "
            "la demande avant son acceptation."
        )
    if are_contacts(contact_request.sender_id, contact_request.receiver_id):
        raise ValueError("Ce contact existe déjà.")

    first_id, second_id = get_contact_pair(
        contact_request.sender_id, contact_request.receiver_id
    )
    db.session.add(Contact(user_id=first_id, contact_user_id=second_id))
    contact_request.status = "accepted"
    db.session.commit()


def reject_contact_request(contact_request, receiver):
    if contact_request.receiver_id != receiver.id:
        raise PermissionError("Tu ne peux pas refuser cette demande.")
    if contact_request.status != "pending":
        raise ValueError("Cette demande n'est plus en attente.")
    contact_request.status = "rejected"
    db.session.commit()


def cancel_contact_request(contact_request, sender):
    if contact_request.sender_id != sender.id:
        raise PermissionError("Tu ne peux pas annuler cette demande.")
    if contact_request.status != "pending":
        raise ValueError("Cette demande n'est plus en attente.")
    contact_request.status = "cancelled"
    db.session.commit()
