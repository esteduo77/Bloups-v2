from itsdangerous import URLSafeTimedSerializer, BadSignature
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


def hash_password(password):
    return generate_password_hash(
        password,
        method="scrypt"
    )


def verify_password(password, password_hash):
    return check_password_hash(password_hash, password)


def create_token(secret_key, purpose, user_id):
    serializer = URLSafeTimedSerializer(secret_key)

    return serializer.dumps({
        "user_id": user_id,
        "purpose": purpose
    })


def verify_token(secret_key, token, purpose, max_age=3600):
    serializer = URLSafeTimedSerializer(secret_key)

    try:
        data = serializer.loads(token, max_age=max_age)

        if data.get("purpose") != purpose:
            return None

        return data.get("user_id")

    except (BadSignature, TypeError, ValueError):
        return None
