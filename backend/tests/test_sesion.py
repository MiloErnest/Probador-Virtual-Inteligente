"""Ep5-Hu6: la sesión del navegador en una cookie `httpOnly`, no en `localStorage`."""

from fastapi.testclient import TestClient

from app.api.deps import CABECERA_ANTI_CSRF, COOKIE_DE_SESION
from tests.conftest import REGISTERED_USER


def _entrar(client: TestClient):
    assert client.post("/api/users", json=REGISTERED_USER).status_code == 201
    return client.post(
        "/api/auth/login",
        json={"email": REGISTERED_USER["email"], "password": REGISTERED_USER["password"]},
    )


def test_el_login_deja_la_sesion_en_una_cookie_httponly(client: TestClient) -> None:
    respuesta = _entrar(client)
    assert respuesta.status_code == 200
    cabecera = respuesta.headers["set-cookie"]
    assert cabecera.startswith(f"{COOKIE_DE_SESION}=")
    assert "HttpOnly" in cabecera, "ningún script de la página puede leerla"
    assert "SameSite=lax" in cabecera
    assert "Path=/api" in cabecera


def test_con_la_cookie_basta_para_saber_quien_soy(client: TestClient) -> None:
    _entrar(client)
    # Sin cabecera Authorization: solo la cookie que guardó el cliente.
    yo = client.get("/api/auth/me")
    assert yo.status_code == 200
    assert yo.json()["email"] == REGISTERED_USER["email"]


def test_con_la_cookie_una_peticion_que_cambia_algo_exige_la_cabecera_anti_csrf(
    client: TestClient,
) -> None:
    _entrar(client)
    sin_cabecera = client.post("/api/fabrics", json={"name": "Desde otra web"})
    assert sin_cabecera.status_code == 401, "una página ajena no puede usar la sesión"

    con_cabecera = client.post(
        "/api/fabrics", json={"name": "Desde la aplicación"}, headers={CABECERA_ANTI_CSRF: "1"}
    )
    assert con_cabecera.status_code == 201, con_cabecera.text


def test_cerrar_sesion_borra_la_cookie(client: TestClient) -> None:
    _entrar(client)
    assert client.get("/api/auth/me").status_code == 200

    salida = client.post("/api/auth/logout")
    assert salida.status_code == 204
    assert f"{COOKIE_DE_SESION}=" in salida.headers["set-cookie"]
    assert "Max-Age=0" in salida.headers["set-cookie"]

    assert client.get("/api/auth/me").status_code == 401


def test_las_rutas_privadas_siguen_cerradas_sin_sesion(client: TestClient) -> None:
    for ruta in ("/api/auth/me", "/api/my-fabrics", "/api/trials", "/api/garment-uploads"):
        assert client.get(ruta).status_code == 401, ruta


def test_una_cookie_falsa_responde_igual_que_ninguna(client: TestClient) -> None:
    client.cookies.set(COOKIE_DE_SESION, "esto.no.vale", path="/api")
    falsa = client.get("/api/auth/me")
    client.cookies.clear()
    ninguna = client.get("/api/auth/me")
    assert falsa.status_code == ninguna.status_code == 401
    assert falsa.json() == ninguna.json()
