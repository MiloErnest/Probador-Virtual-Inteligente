"""Generación e iteración de diseños, y probarse un diseño (Fase 2).

Como en las pruebas virtuales, `TestClient` ejecuta las tareas de fondo de
forma síncrona al terminar la petición: al volver del `post` el diseño ya está
generado, aunque la respuesta recibida dijera `pending`.
"""

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, make_image_bytes, register_and_login


def crear_diseno(client: TestClient, prompt: str = "vestido largo rojo de gala"):
    return client.post("/api/designs", json={"prompt": prompt})


def diseno_listo(client: TestClient, prompt: str = "vestido largo rojo de gala") -> dict:
    """Crea un diseño y devuelve su estado ya generado."""
    creado = crear_diseno(client, prompt)
    assert creado.status_code == 202, creado.text
    return client.get(f"/api/designs/{creado.json()['id']}").json()


# --- Generación --------------------------------------------------------------


def test_creating_a_design_returns_accepted_and_pending(auth_client: TestClient) -> None:
    response = crear_diseno(auth_client)

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["image_url"] is None
    assert body["parent_id"] is None


def test_the_background_task_generates_the_image(auth_client: TestClient) -> None:
    design = diseno_listo(auth_client)

    assert design["status"] == "completed", design.get("error_message")
    assert design["image_url"] is not None
    assert "/media/designs/" in design["image_url"]
    assert design["provider"] == "mock-design"


def test_the_prompt_is_stored_verbatim(auth_client: TestClient) -> None:
    # Se guarda literal para poder reproducir la generación y mostrarla en el
    # historial.
    design = diseno_listo(auth_client, "abrigo largo de lana verde")

    assert design["prompt"] == "abrigo largo de lana verde"


def test_a_too_short_prompt_is_rejected(auth_client: TestClient) -> None:
    assert auth_client.post("/api/designs", json={"prompt": "a"}).status_code == 422


def test_a_blank_prompt_is_rejected(auth_client: TestClient) -> None:
    assert auth_client.post("/api/designs", json={"prompt": "   "}).status_code == 422


def test_designs_are_listed_newest_first(auth_client: TestClient) -> None:
    primero = diseno_listo(auth_client, "camisa blanca de lino")["id"]
    segundo = diseno_listo(auth_client, "pantalon azul ancho")["id"]

    listado = auth_client.get("/api/designs").json()

    assert [d["id"] for d in listado] == [segundo, primero]


# --- Iteración ---------------------------------------------------------------


def test_refining_creates_a_new_design_pointing_at_its_parent(
    auth_client: TestClient,
) -> None:
    padre = diseno_listo(auth_client)

    response = auth_client.post(
        f"/api/designs/{padre['id']}/refine", json={"refinement": "que sea azul"}
    )

    assert response.status_code == 202, response.text
    hijo = response.json()
    assert hijo["parent_id"] == padre["id"]
    assert hijo["refinement"] == "que sea azul"
    # El texto original se hereda: el usuario no lo reescribe.
    assert hijo["prompt"] == padre["prompt"]


def test_refining_never_overwrites_the_original(auth_client: TestClient) -> None:
    """Nunca se pierde una versión que gustaba más."""
    padre = diseno_listo(auth_client)

    auth_client.post(f"/api/designs/{padre['id']}/refine", json={"refinement": "mas corto"})

    sigue = auth_client.get(f"/api/designs/{padre['id']}").json()
    assert sigue["image_url"] == padre["image_url"]
    assert sigue["status"] == "completed"


def test_the_iteration_produces_a_different_image(auth_client: TestClient) -> None:
    padre = diseno_listo(auth_client)

    hijo_id = auth_client.post(
        f"/api/designs/{padre['id']}/refine", json={"refinement": "que sea verde"}
    ).json()["id"]
    hijo = auth_client.get(f"/api/designs/{hijo_id}").json()

    assert hijo["status"] == "completed", hijo.get("error_message")
    assert hijo["image_url"] != padre["image_url"]


def test_cannot_refine_a_design_that_is_not_generated_yet(
    auth_client: TestClient, monkeypatch
) -> None:
    # Se crea el diseño sin dejar que la tarea de fondo lo complete.
    from app.api.deps import get_design_runner
    from app.main import app

    app.dependency_overrides[get_design_runner] = lambda: (lambda _id: None)
    pendiente = crear_diseno(auth_client).json()

    response = auth_client.post(
        f"/api/designs/{pendiente['id']}/refine", json={"refinement": "azul"}
    )

    assert response.status_code == 422
    assert "generado" in response.json()["detail"].lower()


def test_cannot_refine_someone_elses_design(auth_client: TestClient) -> None:
    ajeno = diseno_listo(auth_client)
    _, otro_token = register_and_login(auth_client, email="otro@example.com")

    response = auth_client.post(
        f"/api/designs/{ajeno['id']}/refine",
        json={"refinement": "azul"},
        headers=auth_headers(otro_token),
    )

    assert response.status_code == 404


# --- Autenticación y aislamiento ---------------------------------------------


def test_designs_require_authentication(client: TestClient) -> None:
    assert client.post("/api/designs", json={"prompt": "vestido rojo"}).status_code == 401
    assert client.get("/api/designs").status_code == 401


def test_you_only_see_your_own_designs(auth_client: TestClient) -> None:
    diseno_listo(auth_client)
    _, otro_token = register_and_login(auth_client, email="otro@example.com")

    assert auth_client.get("/api/designs", headers=auth_headers(otro_token)).json() == []


def test_another_users_design_looks_nonexistent(auth_client: TestClient) -> None:
    mio = diseno_listo(auth_client)
    _, otro_token = register_and_login(auth_client, email="otro@example.com")

    response = auth_client.get(
        f"/api/designs/{mio['id']}", headers=auth_headers(otro_token)
    )

    assert response.status_code == 404


# --- Conexión Diseño -> Try-On -----------------------------------------------


def test_you_can_try_on_your_own_design(auth_client: TestClient) -> None:
    """El puente entre la Fase 2 y la Fase 1."""
    design = diseno_listo(auth_client)

    response = auth_client.post(
        "/api/try-on-sessions",
        data={"design_id": design["id"]},
        files={"photo": ("yo.png", make_image_bytes(), "image/png")},
    )

    assert response.status_code == 202, response.text
    prueba = response.json()
    assert prueba["design_id"] == design["id"]
    assert prueba["garment_id"] is None

    completada = auth_client.get(f"/api/try-on-sessions/{prueba['id']}").json()
    assert completada["status"] == "completed", completada.get("error_message")
    assert completada["output_image_url"] is not None


def test_a_try_on_needs_exactly_one_source(
    auth_client: TestClient, garment_with_image: dict
) -> None:
    """Ni los dos ni ninguno.

    La base de datos lo impone con una CHECK; la API lo explica antes.
    """
    design = diseno_listo(auth_client)
    foto = ("yo.png", make_image_bytes(), "image/png")

    ninguno = auth_client.post("/api/try-on-sessions", files={"photo": foto})
    ambos = auth_client.post(
        "/api/try-on-sessions",
        data={"garment_id": garment_with_image["id"], "design_id": design["id"]},
        files={"photo": foto},
    )

    assert ninguno.status_code == 422
    assert ambos.status_code == 422


def test_you_cannot_try_on_someone_elses_design(auth_client: TestClient) -> None:
    ajeno = diseno_listo(auth_client)
    _, otro_token = register_and_login(auth_client, email="otro@example.com")

    response = auth_client.post(
        "/api/try-on-sessions",
        data={"design_id": ajeno["id"]},
        files={"photo": ("yo.png", make_image_bytes(), "image/png")},
        headers=auth_headers(otro_token),
    )

    assert response.status_code == 404


def test_you_cannot_try_on_a_design_that_is_not_generated_yet(
    auth_client: TestClient,
) -> None:
    from app.api.deps import get_design_runner
    from app.main import app

    app.dependency_overrides[get_design_runner] = lambda: (lambda _id: None)
    pendiente = crear_diseno(auth_client).json()

    response = auth_client.post(
        "/api/try-on-sessions",
        data={"design_id": pendiente["id"]},
        files={"photo": ("yo.png", make_image_bytes(), "image/png")},
    )

    assert response.status_code == 422
