"""Perfil corporal, análisis por foto y recomendación de talla (Fase 3).

La recomendación de talla NO es un simulado: es una comparación real contra
tablas de tallaje, y estas pruebas la ejercitan como tal. Lo simulado es de
dónde salen las medidas, no el cálculo.
"""

import pytest
from fastapi.testclient import TestClient

from app.models.garment import GarmentCategory
from app.models.body_profile import BodyProfile, MeasurementSource
from app.services.sizing import recommend, size_for
from app.services.sizing import CHEST_CHART, WAIST_CHART
from tests.conftest import auth_headers, make_image_bytes, register_and_login

MEDIDAS = {"height_cm": 175, "chest_cm": 94, "waist_cm": 78, "hips_cm": 100, "inseam_cm": 80}


def perfil(campos: dict | None = None, source=MeasurementSource.MANUAL) -> BodyProfile:
    """Perfil suelto, sin base de datos, para probar el cálculo de talla."""
    p = BodyProfile(user_id=1, source=source)
    for k, v in (campos or {}).items():
        setattr(p, k, v)
    return p


# --- Cálculo de talla (lógica pura, sin HTTP) --------------------------------


@pytest.mark.parametrize(
    ("pecho", "esperada"),
    [(70, "XS"), (85, "S"), (94, "M"), (102, "L"), (110, "XL"), (130, "XXL")],
)
def test_the_chest_chart_maps_to_the_expected_size(pecho: float, esperada: str) -> None:
    assert size_for(pecho, CHEST_CHART) == esperada


def test_the_boundary_belongs_to_the_smaller_size() -> None:
    """Los rangos son (mín, máx]: el extremo superior entra en su talla.

    Sin esta convención, una medida justo en el límite podría caer en dos
    tallas o en ninguna, según el orden en que se recorra la tabla.
    """
    assert size_for(90.0, CHEST_CHART) == "S"
    assert size_for(90.1, CHEST_CHART) == "M"
    assert size_for(74.0, WAIST_CHART) == "S"


def test_a_top_is_sized_by_the_chest(  ) -> None:
    r = recommend(perfil({"chest_cm": 94, "waist_cm": 120}), GarmentCategory.TOP)

    # La cintura enorme no debe influir: una camisa se talla por pecho.
    assert r.size == "M"
    assert r.based_on == ["chest"]


def test_trousers_are_sized_by_waist_and_hips() -> None:
    r = recommend(perfil({"chest_cm": 70, "waist_cm": 78, "hips_cm": 100}), GarmentCategory.BOTTOM)

    assert set(r.based_on) == {"waist", "hips"}
    # El pecho no participa aunque esté disponible.
    assert "chest" not in r.per_measurement


def test_when_measurements_disagree_the_largest_size_wins() -> None:
    """Una prenda holgada se ajusta; una que no entra, no sirve."""
    r = recommend(
        perfil({"chest_cm": 84, "waist_cm": 78, "hips_cm": 120}), GarmentCategory.DRESS
    )

    assert r.per_measurement == {"chest": "S", "waist": "M", "hips": "XL"}
    assert r.size == "XL"
    # Y se explica, porque si no el usuario no entiende por qué le sale XL.
    assert "mayor" in r.reason.lower()


def test_without_the_needed_measurements_there_is_no_size() -> None:
    """Mejor no responder que inventar una talla."""
    r = recommend(perfil({"height_cm": 175}), GarmentCategory.TOP)

    assert r.size is None
    assert r.confidence == 0.0
    assert "pecho" in r.reason


def test_estimated_measurements_lower_the_confidence() -> None:
    manual = recommend(perfil({"chest_cm": 94}), GarmentCategory.TOP)
    estimado = recommend(
        perfil({"chest_cm": 94}, source=MeasurementSource.ANALYSIS), GarmentCategory.TOP
    )

    assert estimado.confidence < manual.confidence
    assert "estimadas" in estimado.reason


def test_partial_measurements_lower_the_confidence() -> None:
    completo = recommend(
        perfil({"chest_cm": 94, "waist_cm": 78, "hips_cm": 100}), GarmentCategory.DRESS
    )
    parcial = recommend(perfil({"chest_cm": 94}), GarmentCategory.DRESS)

    assert parcial.confidence < completo.confidence


# --- Perfil por HTTP ---------------------------------------------------------


def test_there_is_no_profile_until_you_create_one(auth_client: TestClient) -> None:
    assert auth_client.get("/api/body-profile").status_code == 404


def test_creating_and_reading_the_profile(auth_client: TestClient) -> None:
    creado = auth_client.put("/api/body-profile", json=MEDIDAS)

    assert creado.status_code == 200, creado.text
    assert creado.json()["chest_cm"] == 94
    assert creado.json()["source"] == "manual"
    assert auth_client.get("/api/body-profile").json()["waist_cm"] == 78


def test_updating_is_partial_and_does_not_wipe_other_measurements(
    auth_client: TestClient,
) -> None:
    """Enviar solo la altura no debe borrar el resto."""
    auth_client.put("/api/body-profile", json=MEDIDAS)

    actualizado = auth_client.put("/api/body-profile", json={"height_cm": 180}).json()

    assert actualizado["height_cm"] == 180
    assert actualizado["chest_cm"] == 94


def test_the_profile_is_unique_per_user(auth_client: TestClient) -> None:
    # Dos PUT no crean dos perfiles: el segundo actualiza al primero.
    auth_client.put("/api/body-profile", json=MEDIDAS)
    auth_client.put("/api/body-profile", json={"height_cm": 181})

    assert auth_client.get("/api/body-profile").json()["height_cm"] == 181


@pytest.mark.parametrize(
    "invalido",
    [{"height_cm": 10}, {"height_cm": 400}, {"weight_kg": 5}, {"chest_cm": 300}],
)
def test_absurd_measurements_are_rejected(auth_client: TestClient, invalido: dict) -> None:
    assert auth_client.put("/api/body-profile", json=invalido).status_code == 422


def test_an_empty_update_is_rejected(auth_client: TestClient) -> None:
    assert auth_client.put("/api/body-profile", json={}).status_code == 422


def test_deleting_the_profile(auth_client: TestClient) -> None:
    auth_client.put("/api/body-profile", json=MEDIDAS)

    assert auth_client.delete("/api/body-profile").status_code == 200
    assert auth_client.get("/api/body-profile").status_code == 404


# --- Análisis por foto -------------------------------------------------------


def test_analysing_a_photo_fills_in_the_measurements(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/body-profile/analyse",
        data={"height_cm": 175},
        files={"photo": ("yo.png", make_image_bytes(600, 900), "image/png")},
    )

    assert response.status_code == 200, response.text
    perfil = response.json()
    assert perfil["source"] == "analysis"
    assert perfil["chest_cm"] is not None
    assert perfil["height_cm"] == 175
    # La confianza es baja a propósito: son estimaciones, no mediciones.
    assert 0 < perfil["analysis_confidence"] < 0.5


def test_the_analysis_is_deterministic(auth_client: TestClient) -> None:
    foto = make_image_bytes(600, 900)
    args = {"data": {"height_cm": 175}, "files": {"photo": ("yo.png", foto, "image/png")}}

    primero = auth_client.post("/api/body-profile/analyse", **args).json()
    segundo = auth_client.post("/api/body-profile/analyse", **args).json()

    assert primero["chest_cm"] == segundo["chest_cm"]


def test_a_landscape_photo_is_rejected_with_advice(auth_client: TestClient) -> None:
    """Una foto apaisada casi nunca tiene a alguien de cuerpo entero.

    Avisar es más útil que devolver medidas malas en silencio.
    """
    response = auth_client.post(
        "/api/body-profile/analyse",
        files={"photo": ("paisaje.png", make_image_bytes(900, 400), "image/png")},
    )

    assert response.status_code == 422
    assert "vertical" in response.json()["detail"].lower()


def test_a_file_that_is_not_an_image_is_rejected(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/body-profile/analyse",
        files={"photo": ("trampa.png", b"no soy una imagen", "image/png")},
    )

    assert response.status_code == 422


def test_writing_measurements_by_hand_marks_them_as_manual(
    auth_client: TestClient,
) -> None:
    """Corregir a mano una estimación debe elevar su fiabilidad."""
    auth_client.post(
        "/api/body-profile/analyse",
        files={"photo": ("yo.png", make_image_bytes(600, 900), "image/png")},
    )

    corregido = auth_client.put("/api/body-profile", json={"chest_cm": 96}).json()

    assert corregido["source"] == "manual"


# --- Recomendación por HTTP --------------------------------------------------


def test_size_recommendation_for_a_catalogue_garment(
    auth_client: TestClient, garment_with_image: dict
) -> None:
    auth_client.put("/api/body-profile", json=MEDIDAS)

    response = auth_client.get(
        "/api/body-profile/size-recommendation",
        params={"garment_id": garment_with_image["id"]},
    )

    assert response.status_code == 200, response.text
    cuerpo = response.json()
    # La prenda de la fixture es categoría "top": se talla por pecho.
    assert cuerpo["size"] == "M"
    assert cuerpo["category"] == "top"
    assert cuerpo["reason"]


def test_size_recommendation_for_a_loose_category(auth_client: TestClient) -> None:
    """Existe por los diseños generados: no están en el catálogo."""
    auth_client.put("/api/body-profile", json=MEDIDAS)

    response = auth_client.get(
        "/api/body-profile/size-recommendation", params={"category": "bottom"}
    )

    assert response.status_code == 200
    assert set(response.json()["based_on"]) == {"waist", "hips"}


def test_recommendation_needs_exactly_one_of_garment_or_category(
    auth_client: TestClient, garment_with_image: dict
) -> None:
    auth_client.put("/api/body-profile", json=MEDIDAS)
    url = "/api/body-profile/size-recommendation"

    assert auth_client.get(url).status_code == 422
    assert auth_client.get(
        url, params={"garment_id": garment_with_image["id"], "category": "top"}
    ).status_code == 422


def test_recommendation_without_a_profile_says_so(
    auth_client: TestClient, garment_with_image: dict
) -> None:
    response = auth_client.get(
        "/api/body-profile/size-recommendation",
        params={"garment_id": garment_with_image["id"]},
    )

    assert response.status_code == 404
    assert "perfil" in response.json()["detail"].lower()


# --- Autenticación y aislamiento ---------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/body-profile"),
        ("PUT", "/api/body-profile"),
        ("POST", "/api/body-profile/analyse"),
        ("DELETE", "/api/body-profile"),
        ("GET", "/api/body-profile/size-recommendation"),
    ],
)
def test_the_body_profile_requires_authentication(
    client: TestClient, method: str, path: str
) -> None:
    assert client.request(method, path).status_code == 401


def test_each_user_has_their_own_profile(auth_client: TestClient) -> None:
    """No hay endpoint que acepte un user_id, así que no se puede ni pedir el
    perfil de otro. Esta prueba fija esa garantía."""
    auth_client.put("/api/body-profile", json=MEDIDAS)
    _, otro_token = register_and_login(auth_client, email="otro@example.com")

    ajeno = auth_client.get("/api/body-profile", headers=auth_headers(otro_token))

    assert ajeno.status_code == 404
