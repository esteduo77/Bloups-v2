import os
import smtplib

from email.message import EmailMessage


def send_email(destination, subject, body):
    smtp_host = os.environ.get("BLOOPS_SMTP_HOST")
    smtp_port = int(os.environ.get("BLOOPS_SMTP_PORT", "587"))
    smtp_user = os.environ.get("BLOOPS_SMTP_USER")
    smtp_password = os.environ.get("BLOOPS_SMTP_PASSWORD")
    sender = os.environ.get("BLOOPS_EMAIL_SENDER")

    if not all([
        smtp_host,
        smtp_user,
        smtp_password,
        sender
    ]):
        raise RuntimeError(
            "Le service e-mail BLOOPS n'est pas configuré."
        )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = destination
    message.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(message)
