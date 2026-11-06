def test_espace_famille_redirige_si_non_connecte(client):
    response = client.get("/famille/espace")

    assert response.status_code == 302
    assert "/connexion" in response.location


def test_espace_famille_est_accessible_si_connecte(client, app):
    with client.session_transaction() as session:
        session["user_id"] = 1

    response = client.get("/famille/espace")

    assert response.status_code == 200
    assert b"Mon espace Famille" in response.data
