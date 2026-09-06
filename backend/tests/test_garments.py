"""Catálogo de prendas y subida de imágenes."""

import base64

from fastapi.testclient import TestClient

# PNG válido de 1x1 px, suficiente para ejercitar la ruta de subida.
ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

DRESS = {
    "name": "Vestido de gala rojo",
    "description": "Falda amplia, escote en V.",
    "category": "dress",
}


def test_create_garment(client: TestClient) -> None:
    response = client.post("/api/garments", json=DRESS)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == DRESS["name"]
    assert body["category"] == "dress"
    assert body["active"] is True
    # Recién creada no tiene imagen: el frontend debe tolerar el nulo.
    assert body["image_url"] is None


def test_list_garments_returns_created_ones(client: TestClient) -> None:
    client.post("/api/garments", json=DRESS)

    response = client.get("/api/garments")

    assert response.status_code == 200
    assert [g["name"] for g in response.json()] == [DRESS["name"]]


def test_list_garments_filters_by_category(client: TestClient) -> None:
    client.post("/api/garments", json=DRESS)
    client.post("/api/garments", json={"name": "Camisa", "category": "top"})

    response = client.get("/api/garments", params={"category": "top"})

    assert [g["name"] for g in response.json()] == ["Camisa"]


def test_inactive_garments_are_hidden_by_default(client: TestClient) -> None:
    client.post("/api/garments", json={**DRESS, "active": False})

    assert client.get("/api/garments").json() == []
    assert len(client.get("/api/garments", params={"include_inactive": True}).json()) == 1


def test_upload_image_returns_public_url(client: TestClient) -> None:
    garment_id = client.post("/api/garments", json=DRESS).json()["id"]

    response = client.post(
        f"/api/garments/{garment_id}/image",
        files={"file": ("vestido.png", ONE_PIXEL_PNG, "image/png")},
    )

    assert response.status_code == 200
    image_url = response.json()["image_url"]
    assert image_url is not None
    assert "/media/garments/" in image_url
    assert image_url.endswith(".png")


def test_upload_rejects_unsupported_file_type(client: TestClient) -> None:
    garment_id = client.post("/api/garments", json=DRESS).json()["id"]

    response = client.post(
        f"/api/garments/{garment_id}/image",
        files={"file": ("notas.txt", b"no soy una imagen", "text/plain")},
    )

    assert response.status_code == 422


def test_upload_to_unknown_garment_returns_not_found(client: TestClient) -> None:
    response = client.post(
        "/api/garments/9999/image",
        files={"file": ("vestido.png", ONE_PIXEL_PNG, "image/png")},
    )

    assert response.status_code == 404


def test_try_on_history_is_empty_for_a_new_user(client: TestClient) -> None:
    response = client.get("/api/try-on-sessions", params={"user_id": 1})

    assert response.status_code == 200
    assert response.json() == []
