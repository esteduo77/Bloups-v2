import os

os.environ.setdefault("BLOOPS_SECRET_KEY", "cle-test-bloops")
os.environ.setdefault("BLOOPS_DATABASE_URL", "sqlite:///:memory:")

import pytest

from app import create_app


@pytest.fixture
def app():
    application = create_app({
        "TESTING": True,
        "SECRET_KEY": "cle-test-bloops",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": True,
        "WTF_CSRF_CHECK_DEFAULT": True,
        "RATELIMIT_ENABLED": False,
    })
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.mark.parametrize("route", [
    "/famille/creer",
    "/famille/1/inviter-enfant",
    "/famille/invitations/1/accepter",
    "/famille/1/membres/1/retirer",
    "/famille/1/inviter-responsable",
    "/famille/invitations/1/accepter-responsable",
    "/famille/invitations/1/refuser-responsable",
])
def test_routes_familiales_post_exigent_csrf(client, route):
    response = client.post(route, json={})

    assert response.status_code == 400
