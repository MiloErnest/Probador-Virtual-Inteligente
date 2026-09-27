"""El probador: la foto de una persona con una prenda del taller puesta.

Ninguna prueba llama a Hugging Face ni descarga el analizador. El modelo y el
analizador se sustituyen por dobles que hacen lo que se midió que hacen los de
verdad: el modelo pinta la prenda nueva Y cambia cosas que no debe —el fondo—,
y el analizador distingue la ropa del resto.
"""

import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import settings
from app.models.try_on import GarmentCategory
from app.probador import partes as P
from app.probador import vestir as V
from app.probador.conservar import zona_editable
from app.probador.fashn import traducir_error
from tests.conftest import auth_headers, make_image_bytes, register_and_login

CAMISA = (30, 40, 120)  # la camisa azul marino de la persona
PIEL = (200, 150, 120)
FONDO = (215, 215, 210)
PRENDA_NUEVA = (200, 30, 30)


def _foto_de_persona(ancho: int = 300, alto: int = 450) -> Image.Image:
    """Una «persona»: brazos de piel y una camisa azul, sobre un fondo liso."""
    px = np.full((alto, ancho, 3), FONDO, dtype=np.uint8)
    px[60:420, 110:190] = PIEL  # cuerpo y cara
    px[140:300, 80:220] = CAMISA  # camisa, con mangas
    return Image.fromarray(px)


def _jpeg(imagen: Image.Image, **kwargs) -> bytes:
    buffer = io.BytesIO()
    imagen.save(buffer, format="JPEG", quality=95, **kwargs)
    return buffer.getvalue()


def _etiquetar_por_color(imagen: Image.Image, tamano: tuple[int, int]) -> np.ndarray:
    """Doble del analizador: la ropa por su color, la piel como cuerpo."""
    px = np.asarray(imagen.convert("RGB").resize(tamano, Image.Resampling.NEAREST), dtype=np.int32)
    etiquetas = np.full(px.shape[:2], P.FONDO, dtype=np.uint8)
    for color, clase in ((PIEL, P.CARA), (CAMISA, P.ROPA_ARRIBA), (PRENDA_NUEVA, P.ROPA_ARRIBA)):
        cerca = np.abs(px - np.array(color)).sum(axis=2) < 60
        etiquetas[cerca] = clase
    return etiquetas


class ModeloQueInventa:
    """Pinta la prenda nueva donde estaba la camisa y, de paso, cambia el fondo.

    Es lo que se midió con FASHN VTON: regenera una caja alrededor del torso e
    inventa dentro de ella.
    """

    nombre = "doble-de-prueba"

    def vestir(self, peticion):
        px = np.asarray(peticion.persona.convert("RGB")).copy()
        camisa = np.abs(px.astype(np.int32) - np.array(CAMISA)).sum(axis=2) < 60
        px[camisa] = PRENDA_NUEVA
        alto = px.shape[0]
        px[: alto // 6, : px.shape[1] // 3] = (20, 200, 20)  # un «cuadro» inventado
        return Image.fromarray(px).resize((px.shape[1] // 2, alto // 2))


@pytest.fixture
def modelo_falso(monkeypatch):
    monkeypatch.setattr(settings, "VTO_PROVIDER", "doble")
    monkeypatch.setattr(V, "modelo_configurado", lambda: ModeloQueInventa())
    monkeypatch.setattr(P, "etiquetar", _etiquetar_por_color)


@pytest.fixture
def foto(auth_client: TestClient) -> dict:
    respuesta = auth_client.post(
        "/api/person-photos", files={"file": ("yo.jpg", _jpeg(_foto_de_persona()), "image/jpeg")}
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


# --- La foto de la persona ------------------------------------------------------


def test_la_foto_se_endereza_y_pierde_los_metadatos(auth_client: TestClient, storage) -> None:
    """Un móvil guarda la foto de lado y apunta el giro en EXIF.

    Sin enderezarla, el modelo recibiría a la persona tumbada. Y al volver a
    codificarla no viaja nada de lo que traía: ni el giro, ni la ubicación.
    """
    exif = Image.Exif()
    exif[0x0112] = 6  # girar 90°
    exif[0x010F] = "Telefono de prueba"
    tumbada = Image.new("RGB", (400, 300), "navy")

    respuesta = auth_client.post(
        "/api/person-photos",
        files={"file": ("yo.jpg", _jpeg(tumbada, exif=exif.tobytes()), "image/jpeg")},
    )
    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert (cuerpo["width"], cuerpo["height"]) == (300, 400)

    clave = cuerpo["image_url"].split("/media/")[1]
    guardada = Image.open(io.BytesIO(storage.read(clave)))
    assert not dict(guardada.getexif()), "la foto guardada no lleva metadatos"


def test_una_foto_enorme_se_guarda_a_tamano_razonable(auth_client: TestClient) -> None:
    respuesta = auth_client.post(
        "/api/person-photos",
        files={"file": ("yo.png", make_image_bytes(3000, 2200), "image/png")},
    )
    assert respuesta.status_code == 201, respuesta.text
    assert max(respuesta.json()["width"], respuesta.json()["height"]) == settings.PERSON_PHOTO_MAX_SIDE


def test_la_foto_de_otro_no_se_ve_ni_se_borra(client: TestClient, foto: dict) -> None:
    _, token = register_and_login(client, email="otra@example.com")
    ajeno = auth_headers(token)
    assert client.get("/api/person-photos", headers=ajeno).json() == []
    assert client.delete(f"/api/person-photos/{foto['id']}", headers=ajeno).status_code == 404


# --- La prueba --------------------------------------------------------------------


def test_la_prenda_sale_de_una_sola_fuente(auth_client: TestClient, foto: dict) -> None:
    sin_prenda = auth_client.post("/api/try-ons", json={"person_photo_id": foto["id"]})
    assert sin_prenda.status_code == 422
    con_dos = auth_client.post(
        "/api/try-ons",
        json={"person_photo_id": foto["id"], "fabric_trial_id": 1, "garment_upload_id": 1},
    )
    assert con_dos.status_code == 422


def test_sin_probador_activado_la_prueba_dice_como_activarlo(
    auth_client: TestClient, foto: dict, uploaded_garment: dict
) -> None:
    respuesta = auth_client.post(
        "/api/try-ons",
        json={"person_photo_id": foto["id"], "garment_upload_id": uploaded_garment["id"]},
    )
    assert respuesta.status_code == 202, respuesta.text
    prueba = auth_client.get(f"/api/try-ons/{respuesta.json()['id']}").json()
    assert prueba["status"] == "failed"
    assert "VTO_PROVIDER=fashn" in prueba["error_message"]


def test_la_persona_se_conserva_y_solo_cambia_la_prenda(
    auth_client: TestClient, foto: dict, uploaded_garment: dict, storage, modelo_falso
) -> None:
    """La garantía del probador, de punta a punta por la API.

    El modelo pinta la prenda nueva e inventa un cuadro en el fondo. En el
    resultado, la prenda está y el cuadro no: fuera de la ropa, los píxeles son
    los de la foto original.
    """
    creada = auth_client.post(
        "/api/try-ons",
        json={
            "person_photo_id": foto["id"],
            "garment_upload_id": uploaded_garment["id"],
            "category": "top",
        },
    )
    assert creada.status_code == 202, creada.text
    prueba = auth_client.get(f"/api/try-ons/{creada.json()['id']}").json()
    assert prueba["status"] == "completed", prueba["error_message"]
    assert prueba["provider"] == "doble-de-prueba"
    assert prueba["garment_image_url"] and prueba["person_image_url"]
    assert 0 < prueba["edited_fraction"] < 0.5

    salida = np.asarray(
        Image.open(io.BytesIO(storage.read(prueba["output_image_url"].split("/media/")[1]))),
        dtype=np.int32,
    )
    original = np.asarray(_foto_de_persona(), dtype=np.int32)
    assert salida.shape == original.shape

    torso = salida[180:260, 120:180].reshape(-1, 3).mean(axis=0)
    assert np.abs(torso - np.array(PRENDA_NUEVA)).sum() < 60, "la prenda nueva está puesta"

    # El «cuadro» que inventó el modelo estaba arriba a la izquierda del
    # encuadre. Ahí la foto sigue siendo la original (salvo el ruido del JPEG).
    esquina = np.abs(salida[:120, :] - original[:120, :]).mean()
    assert esquina < 4, f"el fondo inventado no llega al resultado ({esquina:.1f})"
    cara = np.abs(salida[70:130, 120:180] - original[70:130, 120:180]).mean()
    assert cara < 4, "la cara es la de la foto"
    assert "fuera de la prenda" in (prueba["notice"] or "")


def test_de_una_prueba_de_tela_se_usa_la_imagen_ya_generada(
    auth_client: TestClient, foto: dict, uploaded_garment: dict, fabric_with_texture: dict,
    storage, modelo_falso,
) -> None:
    """No se vuelve a vestir la prenda: se recorta la imagen de la prueba."""
    tela = auth_client.post(
        "/api/trials",
        json={"garment_upload_id": uploaded_garment["id"], "fabric_id": fabric_with_texture["id"]},
    ).json()
    tela = auth_client.get(f"/api/trials/{tela['id']}").json()
    assert tela["status"] == "completed"

    creada = auth_client.post(
        "/api/try-ons", json={"person_photo_id": foto["id"], "fabric_trial_id": tela["id"]}
    )
    prueba = auth_client.get(f"/api/try-ons/{creada.json()['id']}").json()
    assert prueba["status"] == "completed", prueba["error_message"]

    # La prenda enviada son los píxeles de la prueba de tela, recortados.
    enviada = np.asarray(
        Image.open(io.BytesIO(storage.read(prueba["garment_image_url"].split("/media/")[1]))).convert("RGB"),
        dtype=np.float32,
    )
    generada = np.asarray(
        Image.open(io.BytesIO(storage.read(tela["output_image_url"].split("/media/")[1]))).convert("RGB"),
        dtype=np.float32,
    )
    centro_enviada = enviada[enviada.shape[0] // 2, enviada.shape[1] // 2]
    centro_generada = generada[generada.shape[0] // 2, generada.shape[1] // 2]
    assert np.abs(centro_enviada - centro_generada).max() < 3


def test_no_se_puede_usar_la_prenda_de_otro(
    client: TestClient, uploaded_garment: dict
) -> None:
    _, token = register_and_login(client, email="otra@example.com")
    ajeno = auth_headers(token)
    suya = client.post(
        "/api/person-photos",
        files={"file": ("yo.jpg", _jpeg(_foto_de_persona()), "image/jpeg")},
        headers=ajeno,
    ).json()
    respuesta = client.post(
        "/api/try-ons",
        json={"person_photo_id": suya["id"], "garment_upload_id": uploaded_garment["id"]},
        headers=ajeno,
    )
    assert respuesta.status_code == 404


def test_borrar_la_foto_borra_sus_pruebas_y_sus_archivos(
    auth_client: TestClient, foto: dict, uploaded_garment: dict, storage, modelo_falso
) -> None:
    creada = auth_client.post(
        "/api/try-ons",
        json={"person_photo_id": foto["id"], "garment_upload_id": uploaded_garment["id"]},
    ).json()
    prueba = auth_client.get(f"/api/try-ons/{creada['id']}").json()
    claves = [prueba[k].split("/media/")[1] for k in ("output_image_url", "garment_image_url")]

    assert auth_client.delete(f"/api/person-photos/{foto['id']}").status_code == 200
    assert auth_client.get(f"/api/try-ons/{creada['id']}").status_code == 404
    for clave in claves:
        with pytest.raises(FileNotFoundError):
            storage.read(clave)


# --- Las piezas, por separado -------------------------------------------------------


def test_la_cara_y_el_fondo_nunca_entran_aunque_el_modelo_los_cambie() -> None:
    alto, ancho = 200, 200
    persona = np.full((alto, ancho, 3), 200, dtype=np.float32)
    generada = persona.copy()
    generada[:] = 60  # el modelo lo ha cambiado TODO
    partes = np.full((alto, ancho), P.FONDO, dtype=np.uint8)
    partes[20:60, 80:120] = P.CARA
    partes[70:150, 60:140] = P.ROPA_ARRIBA
    partes[70:150, 40:60] = P.BRAZO_IZQ

    zona = zona_editable(persona, generada, partes, partes, GarmentCategory.TOP)
    assert zona.alfa[100, 100] == 1.0, "la ropa se toma del modelo"
    assert zona.alfa[110, 50] > 0.99, "el brazo cambió, así que también"
    assert zona.alfa[40, 100] == 0.0, "la cara nunca"
    assert zona.alfa[190, 10] == 0.0, "el fondo nunca"
    assert zona.descartado > 0.5


def test_un_brazo_que_no_cambia_se_queda_con_sus_pixeles() -> None:
    alto, ancho = 200, 200
    persona = np.full((alto, ancho, 3), 200, dtype=np.float32)
    generada = persona.copy()
    generada[70:150, 60:140] = 30  # solo cambia la ropa
    partes = np.full((alto, ancho), P.FONDO, dtype=np.uint8)
    partes[70:150, 60:140] = P.ROPA_ARRIBA
    partes[70:190, 10:40] = P.BRAZO_IZQ

    zona = zona_editable(persona, generada, partes, partes, GarmentCategory.TOP)
    assert zona.alfa[170, 25] == 0.0


def test_en_una_camisa_el_pantalon_no_se_toca() -> None:
    alto, ancho = 200, 200
    persona = np.full((alto, ancho, 3), 200, dtype=np.float32)
    generada = persona.copy()
    generada[:] = 60
    partes = np.full((alto, ancho), P.FONDO, dtype=np.uint8)
    partes[40:100, 60:140] = P.ROPA_ARRIBA
    partes[110:190, 60:140] = P.PANTALON

    arriba = zona_editable(persona, generada, partes, partes, GarmentCategory.TOP)
    assert arriba.alfa[160, 100] == 0.0
    entera = zona_editable(persona, generada, partes, partes, GarmentCategory.FULL)
    assert entera.alfa[160, 100] == 1.0


def test_el_encuadre_tiene_la_proporcion_del_modelo_y_no_se_sale() -> None:
    figura = np.zeros((400, 600), dtype=bool)
    figura[100:380, 250:330] = True
    x0, y0, x1, y1 = V._encuadre(figura, 2.0, (1200, 800))
    assert 0 <= x0 < x1 <= 1200 and 0 <= y0 < y1 <= 800
    assert abs((x1 - x0) / (y1 - y0) - V.PROPORCION) < 0.01


def test_la_cuota_agotada_se_explica_con_lo_que_hay_que_hacer(monkeypatch) -> None:
    monkeypatch.setattr(settings, "HF_TOKEN", "")
    mensaje = traducir_error(
        "You have exceeded your ZeroGPU runs limit. Authenticate with a Hugging Face token"
    )
    assert "HF_TOKEN" in mensaje and "cuota" in mensaje
