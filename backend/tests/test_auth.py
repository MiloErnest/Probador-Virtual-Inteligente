"""Autenticación: login, tokens y protección de endpoints.

Estas pruebas no comprueban solo el camino feliz. La mayor parte verifica lo
que debe FALLAR, que es donde vive el riesgo en una capa de autenticación:
un endpoint que se olvida de pedir el token no da ningún síntoma visible
hasta que alguien lo aprovecha.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from tests.conftest import REGISTERED_USER, auth_headers, register_and_login


# --- Login -------------------------------------------------------------------


def test_login_with_valid_credentials_returns_a_token(client: TestClient) -> None:
    register_and_login(client)

    response = client.post(
        "/api/auth/login",
        json={"email": REGISTERED_USER["email"], "password": REGISTERED_USER["password"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["access_token"]


def test_login_accepts_the_email_in_any_case(client: TestClient) -> None:
    # El registro normaliza el email a minúsculas; el login debe encontrarlo
    # igualmente aunque se escriba con mayúsculas.
    register_and_login(client)

    response = client.post(
        "/api/auth/login",
        json={"email": "ANA@Example.COM", "password": REGISTERED_USER["password"]},
    )

    assert response.status_code == 200


def test_login_with_wrong_password_is_rejected(client: TestClient) -> None:
    register_and_login(client)

    response = client.post(
        "/api/auth/login",
        json={"email": REGISTERED_USER["email"], "password": "otra-contrasena"},
    )

    assert response.status_code == 401


def test_login_with_unknown_email_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "nadie@example.com", "password": "contrasena-segura-1"},
    )

    assert response.status_code == 401


def test_unknown_email_and_wrong_password_are_indistinguishable(
    client: TestClient,
) -> None:
    """No se debe poder averiguar qué correos están registrados.

    Si el mensaje o el código difirieran, el formulario de acceso se
    convertiría en un buscador de cuentas existentes.
    """
    register_and_login(client)

    wrong_password = client.post(
        "/api/auth/login",
        json={"email": REGISTERED_USER["email"], "password": "no-es-esta"},
    )
    unknown_email = client.post(
        "/api/auth/login",
        json={"email": "nadie@example.com", "password": "no-es-esta"},
    )

    assert wrong_password.status_code == unknown_email.status_code
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]


def test_deactivated_account_cannot_log_in(client: TestClient, db_session) -> None:
    from app.models.user import User

    user, _ = register_and_login(client)
    db_session.get(User, user["id"]).is_active = False
    db_session.commit()

    response = client.post(
        "/api/auth/login",
        json={"email": REGISTERED_USER["email"], "password": REGISTERED_USER["password"]},
    )

    assert response.status_code == 401


def test_login_never_returns_the_password_hash(client: TestClient) -> None:
    register_and_login(client)

    response = client.post(
        "/api/auth/login",
        json={"email": REGISTERED_USER["email"], "password": REGISTERED_USER["password"]},
    )

    assert "password_hash" not in response.text


# --- Validación del token ----------------------------------------------------


def test_me_returns_the_authenticated_user(
    client: TestClient, user_token: tuple[dict, str]
) -> None:
    user, token = user_token

    response = client.get("/api/auth/me", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["id"] == user["id"]
    assert response.json()["email"] == REGISTERED_USER["email"]


def test_me_without_a_token_returns_unauthorized(client: TestClient) -> None:
    response = client.get("/api/auth/me")

    # 401, no 403: no es que no tenga permiso, es que no se ha identificado.
    assert response.status_code == 401
    # Cabecera exigida por el estándar HTTP en toda respuesta 401.
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_a_malformed_token_is_rejected(client: TestClient) -> None:
    response = client.get("/api/auth/me", headers=auth_headers("esto-no-es-un-jwt"))

    assert response.status_code == 401


def test_a_tampered_signature_is_rejected(
    client: TestClient, user_token: tuple[dict, str]
) -> None:
    _, token = user_token
    tampered = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")

    response = client.get("/api/auth/me", headers=auth_headers(tampered))

    assert response.status_code == 401


def test_an_expired_token_is_rejected(
    client: TestClient, user_token: tuple[dict, str]
) -> None:
    user, _ = user_token
    expired, _ = create_access_token(user["id"], expires_minutes=-1)

    response = client.get("/api/auth/me", headers=auth_headers(expired))

    assert response.status_code == 401


def test_a_token_for_a_nonexistent_user_is_rejected(client: TestClient) -> None:
    # El usuario podría haberse borrado después de emitir el token. Por eso se
    # relee de la base en cada petición en vez de confiar en el token.
    orphan, _ = create_access_token(9999)

    response = client.get("/api/auth/me", headers=auth_headers(orphan))

    assert response.status_code == 401


def test_a_deactivated_user_loses_access_with_a_still_valid_token(
    client: TestClient, user_token: tuple[dict, str], db_session
) -> None:
    from app.models.user import User

    user, token = user_token
    assert client.get("/api/auth/me", headers=auth_headers(token)).status_code == 200

    db_session.get(User, user["id"]).is_active = False
    db_session.commit()

    # Sin lista de revocación, el token sigue siendo criptográficamente
    # válido; lo que corta el acceso es comprobar `is_active` en cada petición.
    assert client.get("/api/auth/me", headers=auth_headers(token)).status_code == 401


# --- Endpoints protegidos ----------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/auth/me"),
        ("GET", "/api/users/1"),
        ("GET", "/api/try-on-sessions"),
        ("GET", "/api/try-on-sessions/1"),
        ("POST", "/api/garments"),
        ("POST", "/api/garments/1/image"),
    ],
)
def test_protected_endpoints_reject_anonymous_requests(
    client: TestClient, method: str, path: str
) -> None:
    """Inventario explícito de lo que exige token.

    Escrito como lista para que añadir un endpoint protegido sea añadir una
    línea aquí, y para que quitar la protección de uno rompa la suite en vez
    de pasar inadvertido.
    """
    response = client.request(method, path)

    assert response.status_code == 401, f"{method} {path} no exige autenticación"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/health"),
        ("GET", "/api/garments"),
    ],
)
def test_public_endpoints_stay_public(
    client: TestClient, method: str, path: str
) -> None:
    """El catálogo y el estado del sistema se consultan sin cuenta."""
    response = client.request(method, path)

    assert response.status_code == 200


def test_the_user_list_endpoint_no_longer_exists(client: TestClient) -> None:
    # Devolvía todos los usuarios con sus correos sin pedir nada. Se eliminó
    # en la Etapa 2; esta prueba impide que vuelva por descuido.
    assert client.get("/api/users").status_code == 405


# --- Aislamiento entre usuarios ----------------------------------------------


def test_a_user_cannot_read_another_users_account(
    client: TestClient, user_token: tuple[dict, str]
) -> None:
    _, token = user_token
    other, _ = register_and_login(client, email="otro@example.com")

    response = client.get(f"/api/users/{other['id']}", headers=auth_headers(token))

    # 404 y no 403: un 403 confirmaría que esa cuenta existe.
    assert response.status_code == 404


def test_a_user_can_read_their_own_account(
    client: TestClient, user_token: tuple[dict, str]
) -> None:
    user, token = user_token

    response = client.get(f"/api/users/{user['id']}", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["id"] == user["id"]


def test_the_history_belongs_to_the_token_not_to_a_query_parameter(
    client: TestClient, user_token: tuple[dict, str]
) -> None:
    """El parámetro `?user_id=` era un agujero: se ha eliminado.

    Aunque se envíe, debe ignorarse; el historial que se devuelve es el del
    dueño del token.
    """
    _, token = user_token
    other, _ = register_and_login(client, email="otro@example.com")

    response = client.get(
        "/api/try-on-sessions",
        params={"user_id": other["id"]},
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert all(s["user_id"] != other["id"] for s in response.json())
