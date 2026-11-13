"""Ep9-Hu6: repetir una prueba antigua con el motor de hoy."""

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, make_prenda_bytes, register_and_login


def _probar(client: TestClient, prenda: dict, tela: dict, **extra) -> dict:
    respuesta = client.post(
        "/api/trials", json={"garment_upload_id": prenda["id"], "fabric_id": tela["id"], **extra}
    )
    assert respuesta.status_code == 202, respuesta.text
    return respuesta.json()


def test_repetir_crea_otra_prueba_con_la_misma_prenda_y_tela(
    auth_client: TestClient, uploaded_garment: dict, fabric_with_texture: dict
) -> None:
    antigua = _probar(auth_client, uploaded_garment, fabric_with_texture, repeat_across=11)

    respuesta = auth_client.post(f"/api/trials/{antigua['id']}/repeat")
    assert respuesta.status_code == 202, respuesta.text
    nueva = respuesta.json()

    assert nueva["id"] != antigua["id"]
    assert nueva["garment_upload_id"] == antigua["garment_upload_id"]
    assert nueva["fabric_id"] == antigua["fabric_id"]
    assert nueva["repeat_across"] == 11, "la misma escala del estampado"
    assert auth_client.get(f"/api/trials/{nueva['id']}").json()["status"] == "completed"


def test_la_prueba_antigua_no_se_borra_quedan_las_dos(
    auth_client: TestClient, uploaded_garment: dict, fabric_with_texture: dict
) -> None:
    antigua = _probar(auth_client, uploaded_garment, fabric_with_texture)
    salida_antigua = auth_client.get(f"/api/trials/{antigua['id']}").json()["output_image_url"]

    nueva = auth_client.post(f"/api/trials/{antigua['id']}/repeat").json()

    lista = auth_client.get(f"/api/trials?garment_upload_id={uploaded_garment['id']}").json()
    assert [p["id"] for p in lista] == [nueva["id"], antigua["id"]], "la más reciente, primero"
    conservada = auth_client.get(f"/api/trials/{antigua['id']}").json()
    assert conservada["output_image_url"] == salida_antigua, "la antigua sigue con su imagen"


def test_repetir_nunca_gasta_aunque_la_antigua_fuera_con_ia(
    auth_client: TestClient, uploaded_garment: dict, fabric_with_texture: dict
) -> None:
    antigua = _probar(auth_client, uploaded_garment, fabric_with_texture, method="ai")
    assert antigua["method"] == "ai"

    nueva = auth_client.post(f"/api/trials/{antigua['id']}/repeat").json()
    assert nueva["method"] == "retexture"


def test_repetir_la_prueba_de_otro_responde_404(client: TestClient, user_token) -> None:
    _, token = user_token
    _, token_otro = register_and_login(client, email="repite-ajeno@example.com")
    otro = auth_headers(token_otro)
    tela = client.post("/api/fabrics", json={"name": "Tela para repetir"}, headers=otro).json()
    client.post(
        f"/api/fabrics/{tela['id']}/texture",
        files={"file": ("t.png", make_prenda_bytes(64, 64), "image/png")},
        headers=otro,
    )
    prenda = client.post(
        "/api/garment-uploads",
        data={"name": "Ajena", "kind": "photo"},
        files={"file": ("p.png", make_prenda_bytes(), "image/png")},
        headers=otro,
    ).json()
    prueba = client.post(
        "/api/trials", json={"garment_upload_id": prenda["id"], "fabric_id": tela["id"]}, headers=otro
    ).json()

    respuesta = client.post(f"/api/trials/{prueba['id']}/repeat", headers=auth_headers(token))
    assert respuesta.status_code == 404


def test_no_se_repite_con_una_tela_retirada(
    auth_client: TestClient, uploaded_garment: dict, fabric_with_texture: dict
) -> None:
    antigua = _probar(auth_client, uploaded_garment, fabric_with_texture)
    auth_client.patch(f"/api/fabrics/{fabric_with_texture['id']}", json={"active": False})

    assert auth_client.post(f"/api/trials/{antigua['id']}/repeat").status_code == 404
