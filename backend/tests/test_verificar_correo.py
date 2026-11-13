"""Ep5-Hu7: verificar el correo al registrarse."""

from fastapi.testclient import TestClient

from app.core.security import create_access_token, create_email_verification_token
from tests.conftest import (
    BUZON,
    REGISTERED_USER,
    auth_headers,
    enlace_de_verificacion,
    make_boceto_bytes,
    register_and_login,
)


def test_al_registrarse_se_envia_un_enlace_de_verificacion(client: TestClient) -> None:
    usuario, _ = register_and_login(client, verificar=False)
    assert usuario["email_verified"] is False

    destino, asunto, texto = BUZON[-1]
    assert destino == REGISTERED_USER["email"]
    assert "Confirma tu correo" in asunto
    assert "http://localhost:5173/verificar-correo?token=" in texto
    assert REGISTERED_USER["name"] in texto


def test_abrir_el_enlace_verifica_la_cuenta(client: TestClient) -> None:
    _, token = register_and_login(client, verificar=False)
    enlace = enlace_de_verificacion(REGISTERED_USER["email"])

    respuesta = client.post("/api/auth/verify-email", json={"token": enlace})
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["email_verified"] is True

    yo = client.get("/api/auth/me", headers=auth_headers(token)).json()
    assert yo["email_verified"] is True
    # Abrirlo otra vez no falla.
    assert client.post("/api/auth/verify-email", json={"token": enlace}).status_code == 200


def test_hasta_verificar_no_se_generan_prendas_con_ia(client: TestClient) -> None:
    _, token = register_and_login(client, verificar=False)
    yo = auth_headers(token)

    boceto = client.post(
        "/api/garment-uploads",
        data={"name": "Vestido", "kind": "sketch"},
        files={"file": ("b.png", make_boceto_bytes(), "image/png")},
        headers=yo,
    )
    assert boceto.status_code == 403
    assert "Confirma tu correo" in boceto.json()["detail"]
    assert client.get("/api/garment-uploads", headers=yo).json() == [], "no se guardó nada"


def test_sin_verificar_si_se_prueban_telas_con_el_motor_gratuito(
    client: TestClient, user_token
) -> None:
    """Lo que no cuesta dinero no se bloquea."""
    _, token = register_and_login(client, verificar=False, email="sin-verificar@example.com")
    respuesta = client.post(
        "/api/garment-uploads",
        data={"name": "Camisa", "kind": "photo"},
        files={"file": ("p.png", make_boceto_bytes(), "image/png")},
        headers=auth_headers(token),
    )
    assert respuesta.status_code == 201, respuesta.text


def test_sin_verificar_no_se_prueba_una_tela_con_ia(
    client: TestClient, user_token, fabric_with_texture: dict, uploaded_garment: dict
) -> None:
    # La prenda y la tela son de la cuenta verificada; la prueba la intenta
    # una sin verificar sobre su propia prenda.
    _, token = register_and_login(client, verificar=False, email="sin-ia@example.com")
    prenda = client.post(
        "/api/garment-uploads",
        data={"name": "Mía", "kind": "photo"},
        files={"file": ("p.png", make_boceto_bytes(), "image/png")},
        headers=auth_headers(token),
    ).json()
    respuesta = client.post(
        "/api/trials",
        json={"garment_upload_id": prenda["id"], "fabric_id": fabric_with_texture["id"], "method": "ai"},
        headers=auth_headers(token),
    )
    assert respuesta.status_code == 403


def test_se_puede_pedir_otro_enlace(client: TestClient) -> None:
    _, token = register_and_login(client, verificar=False)
    enviados = len(BUZON)

    respuesta = client.post("/api/auth/resend-verification", headers=auth_headers(token))
    assert respuesta.status_code == 202
    assert len(BUZON) == enviados + 1

    nuevo = enlace_de_verificacion(REGISTERED_USER["email"])
    assert client.post("/api/auth/verify-email", json={"token": nuevo}).status_code == 200


def test_un_enlace_falso_o_de_otro_tipo_no_verifica(client: TestClient) -> None:
    usuario, _ = register_and_login(client, verificar=False)

    for falso in ("esto-no-es-un-token", create_access_token(usuario["id"])[0]):
        respuesta = client.post("/api/auth/verify-email", json={"token": falso})
        assert respuesta.status_code == 422, "un token de SESIÓN no sirve para verificar"


def test_un_enlace_emitido_para_otro_correo_no_vale(client: TestClient) -> None:
    usuario, _ = register_and_login(client, verificar=False)
    ajeno = create_email_verification_token(usuario["id"], "otra-direccion@example.com")
    assert client.post("/api/auth/verify-email", json={"token": ajeno}).status_code == 422


def test_un_token_de_verificacion_no_sirve_para_entrar(client: TestClient) -> None:
    usuario, _ = register_and_login(client, verificar=False)
    enlace = create_email_verification_token(usuario["id"], REGISTERED_USER["email"])
    assert client.get("/api/auth/me", headers=auth_headers(enlace)).status_code == 401
