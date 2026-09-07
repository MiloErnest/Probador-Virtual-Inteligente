"""Creación y procesado de pruebas virtuales (Fase 1).

NOTA SOBRE EL PROCESADO
-----------------------
`TestClient` ejecuta las tareas de fondo de forma **síncrona** en cuanto
termina la petición. Por eso, al volver de `client.post(...)`, la prueba ya
está procesada en la base, aunque la respuesta que se recibió diga `pending`
—se generó antes de que la tarea corriera—.

Es cómodo para probar, pero no es lo que pasa en producción, donde el cliente
tiene que sondear. Ese comportamiento real se verifica a mano contra el
servidor arrancado.
"""

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, make_image_bytes, register_and_login


def crear_prueba(client: TestClient, garment_id: int, photo: bytes | None = None):
    return client.post(
        "/api/try-on-sessions",
        data={"garment_id": garment_id},
        files={"photo": ("yo.png", photo or make_image_bytes(), "image/png")},
    )


# --- Camino feliz ------------------------------------------------------------


def test_creating_a_try_on_returns_accepted_and_pending(
    auth_client: TestClient, garment_with_image: dict
) -> None:
    response = crear_prueba(auth_client, garment_with_image["id"])

    # 202 y no 201: el recurso existe, pero todavía no tiene resultado.
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["garment_id"] == garment_with_image["id"]
    assert body["output_image_url"] is None
    # La foto que se subió sí queda accesible desde el primer momento.
    assert body["input_image_url"] is not None


def test_the_background_task_completes_the_try_on(
    auth_client: TestClient, garment_with_image: dict
) -> None:
    session_id = crear_prueba(auth_client, garment_with_image["id"]).json()["id"]

    response = auth_client.get(f"/api/try-on-sessions/{session_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed", body.get("error_message")
    assert body["output_image_url"] is not None
    assert "/media/results/" in body["output_image_url"]
    assert body["error_message"] is None


def test_the_provider_that_generated_the_result_is_recorded(
    auth_client: TestClient, garment_with_image: dict
) -> None:
    # Saber QUÉ generó cada resultado permite comparar proveedores y
    # reprocesar lo que falló cuando haya más de uno.
    session_id = crear_prueba(auth_client, garment_with_image["id"]).json()["id"]

    assert auth_client.get(f"/api/try-on-sessions/{session_id}").json()["provider"] == (
        "local-preview"
    )


def test_the_result_is_a_real_image_the_size_of_the_photo(
    auth_client: TestClient, garment_with_image: dict, storage
) -> None:
    """El resultado debe ser una imagen abrible, no bytes cualesquiera.

    Y debe conservar el tamaño de la foto original: la prenda se compone
    ENCIMA, no se recorta ni se reencuadra a la persona.
    """
    import io

    from PIL import Image

    session_id = crear_prueba(
        auth_client, garment_with_image["id"], photo=make_image_bytes(400, 600)
    ).json()["id"]

    url = auth_client.get(f"/api/try-on-sessions/{session_id}").json()["output_image_url"]
    # Se lee del almacén, no por HTTP: aquí no se está probando el montaje
    # estático /media, sino lo que el proveedor generó.
    clave = f"results/{url.rsplit('/', 1)[1]}"

    with Image.open(io.BytesIO(storage.read(clave))) as resultado:
        assert resultado.size == (400, 600)


def test_the_try_on_appears_in_the_history(
    auth_client: TestClient, garment_with_image: dict
) -> None:
    session_id = crear_prueba(auth_client, garment_with_image["id"]).json()["id"]

    historial = auth_client.get("/api/try-on-sessions").json()

    assert [s["id"] for s in historial] == [session_id]


# --- Validación de la foto ---------------------------------------------------


def test_a_text_file_disguised_as_png_is_rejected(
    auth_client: TestClient, garment_with_image: dict
) -> None:
    """Regresión de la limitación #6.

    Antes de la Fase 1 se creía la cabecera `Content-Type` que envía el
    cliente. Aquí se declara `image/png` sobre un archivo de texto: debe
    rechazarse igualmente, porque ahora se abre el archivo para comprobarlo.
    """
    response = auth_client.post(
        "/api/try-on-sessions",
        data={"garment_id": garment_with_image["id"]},
        files={"photo": ("trampa.png", b"esto no es una imagen", "image/png")},
    )

    assert response.status_code == 422
    assert "imagen" in response.json()["detail"].lower()


def test_an_empty_file_is_rejected(
    auth_client: TestClient, garment_with_image: dict
) -> None:
    response = auth_client.post(
        "/api/try-on-sessions",
        data={"garment_id": garment_with_image["id"]},
        files={"photo": ("vacio.png", b"", "image/png")},
    )

    assert response.status_code == 422


def test_a_gif_is_rejected_even_though_it_is_a_real_image(
    auth_client: TestClient, garment_with_image: dict
) -> None:
    # Pillow lo abre sin problema, pero GIF no está en la lista admitida:
    # la comprobación es del formato detectado, no de "¿es una imagen?".
    response = auth_client.post(
        "/api/try-on-sessions",
        data={"garment_id": garment_with_image["id"]},
        files={"photo": ("animado.gif", make_image_bytes(fmt="GIF"), "image/gif")},
    )

    assert response.status_code == 422


def test_a_jpeg_photo_is_accepted(
    auth_client: TestClient, garment_with_image: dict
) -> None:
    # El formato más habitual en una cámara de móvil.
    response = auth_client.post(
        "/api/try-on-sessions",
        data={"garment_id": garment_with_image["id"]},
        files={"photo": ("foto.jpg", make_image_bytes(fmt="JPEG"), "image/jpeg")},
    )

    assert response.status_code == 202


# --- Validación de la prenda -------------------------------------------------


def test_an_unknown_garment_returns_not_found(auth_client: TestClient) -> None:
    assert crear_prueba(auth_client, 9999).status_code == 404


def test_a_garment_without_an_image_cannot_be_tried_on(
    auth_client: TestClient,
) -> None:
    sin_imagen = auth_client.post(
        "/api/garments", json={"name": "Prenda sin foto", "category": "top"}
    ).json()

    response = crear_prueba(auth_client, sin_imagen["id"])

    assert response.status_code == 422
    assert "imagen" in response.json()["detail"].lower()


def test_a_retired_garment_cannot_be_tried_on(auth_client: TestClient) -> None:
    retirada = auth_client.post(
        "/api/garments",
        json={"name": "Prenda retirada", "category": "top", "active": False},
    ).json()
    auth_client.post(
        f"/api/garments/{retirada['id']}/image",
        files={"file": ("x.png", make_image_bytes(100, 100), "image/png")},
    )

    response = crear_prueba(auth_client, retirada["id"])

    assert response.status_code == 422
    assert "retirada" in response.json()["detail"].lower()


# --- Autenticación y aislamiento ---------------------------------------------


def test_creating_a_try_on_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/try-on-sessions",
        data={"garment_id": 1},
        files={"photo": ("yo.png", make_image_bytes(), "image/png")},
    )

    assert response.status_code == 401


def test_another_user_cannot_see_the_try_on(
    auth_client: TestClient, garment_with_image: dict
) -> None:
    session_id = crear_prueba(auth_client, garment_with_image["id"]).json()["id"]
    _, otro_token = register_and_login(auth_client, email="otro@example.com")

    response = auth_client.get(
        f"/api/try-on-sessions/{session_id}", headers=auth_headers(otro_token)
    )

    # 404 y no 403: un 403 confirmaría que esa prueba existe.
    assert response.status_code == 404


def test_the_history_only_shows_your_own_try_ons(
    auth_client: TestClient, garment_with_image: dict
) -> None:
    crear_prueba(auth_client, garment_with_image["id"])
    _, otro_token = register_and_login(auth_client, email="otro@example.com")

    ajeno = auth_client.get("/api/try-on-sessions", headers=auth_headers(otro_token))

    assert ajeno.json() == []
