"""Registro y consulta de usuarios.

El registro sigue siendo público por necesidad: no se puede pedir un token
para crear la cuenta con la que se obtiene el token. La consulta, en cambio,
exige autenticación desde la Etapa 2 y solo devuelve la cuenta propia — las
pruebas de aislamiento entre usuarios están en test_auth.py.
"""

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_and_login

VALID_USER = {
    "name": "Ana Torres",
    "email": "ana@example.com",
    "password": "contrasena-segura-1",
}


def test_register_user_returns_created_without_exposing_the_hash(
    client: TestClient,
) -> None:
    response = client.post("/api/users", json=VALID_USER)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ana@example.com"
    assert body["is_active"] is True
    # El hash de la contraseña jamás debe salir por la API.
    assert "password" not in body
    assert "password_hash" not in body


def test_email_is_normalised_to_lowercase(client: TestClient) -> None:
    response = client.post(
        "/api/users", json={**VALID_USER, "email": "Ana@Example.COM"}
    )

    assert response.status_code == 201
    assert response.json()["email"] == "ana@example.com"


def test_duplicate_email_is_rejected_with_conflict(client: TestClient) -> None:
    client.post("/api/users", json=VALID_USER)

    response = client.post("/api/users", json=VALID_USER)

    assert response.status_code == 409


def test_short_password_is_rejected(client: TestClient) -> None:
    response = client.post("/api/users", json={**VALID_USER, "password": "corta"})

    assert response.status_code == 422


def test_password_longer_than_bcrypt_limit_is_rejected(client: TestClient) -> None:
    # bcrypt trunca a 72 bytes en silencio; el schema debe impedirlo antes.
    response = client.post("/api/users", json={**VALID_USER, "password": "a" * 73})

    assert response.status_code == 422


def test_get_user_by_id_requires_a_token(client: TestClient) -> None:
    created = client.post("/api/users", json=VALID_USER).json()

    assert client.get(f"/api/users/{created['id']}").status_code == 401


def test_get_own_user_by_id(client: TestClient) -> None:
    created, token = register_and_login(client)

    response = client.get(f"/api/users/{created['id']}", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_unknown_user_returns_not_found(client: TestClient) -> None:
    _, token = register_and_login(client)

    response = client.get("/api/users/9999", headers=auth_headers(token))

    assert response.status_code == 404
