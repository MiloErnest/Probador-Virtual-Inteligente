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
from app.models.try_on import GarmentCategory, TryOn
from app.probador import partes as P
from app.probador import recomponer
from app.probador import vestir as V
from app.probador.conservar import _solida, paleta_de, zona_editable
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
    variantes: list[int] = []

    def vestir(self, peticion):
        ModeloQueInventa.variantes.append(peticion.variante)
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


def test_ni_la_cara_ni_el_fondo_ni_el_brazo_retocado_entran() -> None:
    """Aunque el modelo lo cambie todo, solo se toma la ropa.

    El brazo es piel en las dos imágenes: si el modelo lo retoca, es un error
    suyo. Pasó de verdad: redibujó la mano que sujetaba el móvil, cortó el
    móvil y dejó un borrón beige, y la regla de entonces —la piel entra donde
    cambie— lo llevó todo al resultado.
    """
    alto, ancho = 200, 200
    persona = np.full((alto, ancho, 3), 200, dtype=np.float32)
    generada = persona.copy()
    generada[:] = 60  # el modelo lo ha cambiado TODO
    partes = np.full((alto, ancho), P.FONDO, dtype=np.uint8)
    partes[20:60, 80:120] = P.CARA
    partes[70:150, 60:140] = P.ROPA_ARRIBA
    partes[70:150, 30:60] = P.BRAZO_IZQ

    zona = zona_editable(persona, generada, partes, partes, GarmentCategory.TOP)
    assert zona.alfa[100, 100] == 1.0, "la ropa se toma del modelo"
    assert zona.alfa[110, 40] == 0.0, "el brazo retocado no"
    assert zona.alfa[40, 100] == 0.0, "la cara nunca"
    assert zona.alfa[190, 10] == 0.0, "el fondo nunca"
    assert zona.descartado > 0.5


def test_la_piel_que_destapa_la_prenda_nueva_si_entra() -> None:
    """Manga larga en la foto, manga corta en la prenda: el brazo nuevo es del modelo."""
    alto, ancho = 200, 200
    persona = np.full((alto, ancho, 3), 200, dtype=np.float32)
    generada = persona.copy()
    generada[70:150, 30:140] = 60
    antes = np.full((alto, ancho), P.FONDO, dtype=np.uint8)
    antes[70:150, 30:140] = P.ROPA_ARRIBA  # la manga larga tapa el brazo
    despues = antes.copy()
    despues[70:150, 30:60] = P.BRAZO_IZQ  # la manga corta lo destapa

    zona = zona_editable(persona, generada, antes, despues, GarmentCategory.TOP)
    assert zona.alfa[110, 40] == 1.0


def test_el_pliegue_de_la_prenda_vieja_que_no_se_reconoce_tambien_se_quita() -> None:
    """Un trozo de la prenda vieja etiquetado como fondo, pegado a ella, entra.

    En la foto del usuario frente al espejo, el pliegue de la camiseta negra
    bajo el codo salió como «fondo» y se quedaba en el resultado. Lo que tiene
    el color de la prenda de al lado y está pegado a ella, es prenda. Pero no
    lo que esté suelto, ni lo que el analizador reconoce como otra cosa.
    """
    alto, ancho = 200, 200
    persona = np.full((alto, ancho, 3), 200, dtype=np.float32)
    partes = np.full((alto, ancho), P.FONDO, dtype=np.uint8)
    persona[70:150, 60:140] = 30
    partes[70:150, 60:140] = P.ROPA_ARRIBA
    persona[150:158, 90:110] = 30  # el pliegue, etiquetado como fondo
    persona[20:40, 10:30] = 30  # algo oscuro en el fondo, suelto
    persona[100:130, 140:160] = 30  # un bolso negro pegado a la camiseta
    partes[100:130, 140:160] = P.BOLSO
    generada = persona.copy()
    generada[70:158, 60:140] = 220

    zona = zona_editable(persona, generada, partes, partes, GarmentCategory.TOP)
    assert zona.alfa[154, 100] == 1.0, "el pliegue es prenda vieja"
    assert zona.alfa[30, 20] == 0.0, "lo oscuro suelto del fondo no"
    assert zona.alfa[115, 152] == 0.0, "el bolso no"


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


# --- Los 502 de Hugging Face ----------------------------------------------------------


class _Respuestas:
    """Doble de `httpx.stream`: devuelve una respuesta de la lista en cada llamada."""

    def __init__(self, codigos: list[int]) -> None:
        self.codigos = list(codigos)
        self.llamadas = 0

    def __call__(self, metodo, url, **kwargs):
        import contextlib

        import httpx

        self.llamadas += 1
        codigo = self.codigos.pop(0)
        respuesta = httpx.Response(codigo, content=b"imagen", request=httpx.Request(metodo, url))
        return contextlib.nullcontext(respuesta)


class _ClienteFalso:
    src_prefixed = "https://espacio.hf.space/gradio_api/"
    headers: dict = {}


def test_un_502_al_descargar_se_reintenta_sin_volver_a_generar(monkeypatch, tmp_path) -> None:
    """Le pasó al usuario: el modelo generó la imagen y la pasarela dio 502 al
    devolverla. Se perdía la imagen, y con ella la cuota gastada."""
    from app.probador import fashn

    respuestas = _Respuestas([502, 502, 200])
    monkeypatch.setattr(fashn.httpx, "stream", respuestas)
    monkeypatch.setattr(fashn, "ESPERAS", (0.0, 0.0, 0.0))

    ruta = fashn._descargar(_ClienteFalso(), {"path": "/tmp/gradio/abc/image.webp"}, tmp_path)
    assert ruta.read_bytes() == b"imagen"
    assert respuestas.llamadas == 3


def test_un_404_al_descargar_no_se_reintenta(monkeypatch, tmp_path) -> None:
    from app.probador import fashn
    from app.textil.errores import ErrorDeMotor

    respuestas = _Respuestas([404, 200])
    monkeypatch.setattr(fashn.httpx, "stream", respuestas)
    monkeypatch.setattr(fashn, "ESPERAS", (0.0, 0.0, 0.0))

    with pytest.raises(ErrorDeMotor, match="404"):
        fashn._descargar(_ClienteFalso(), {"path": "/tmp/gradio/abc/image.webp"}, tmp_path)
    assert respuestas.llamadas == 1


def test_conectar_se_reintenta_si_la_pasarela_falla(monkeypatch) -> None:
    from app.probador import fashn

    monkeypatch.setattr(fashn, "ESPERAS", (0.0, 0.0, 0.0))
    intentos = []

    def cliente(*args, **kwargs):
        intentos.append(kwargs)
        if len(intentos) < 3:
            raise RuntimeError("Server error '502 Bad Gateway' for url '.../config'")
        return "conectado"

    assert fashn._conectar(cliente) == "conectado"
    assert len(intentos) == 3
    assert intentos[0]["download_files"] is False, "la descarga la hace _descargar"


def test_un_502_se_explica_como_fallo_de_hugging_face() -> None:
    mensaje = traducir_error("Server error '502 Bad Gateway' for url 'https://x.hf.space/config'")
    assert "Hugging Face" in mensaje and "no es tu foto" in mensaje


def test_repetir_la_misma_prueba_da_otra_variante(
    auth_client: TestClient, foto: dict, uploaded_garment: dict, modelo_falso
) -> None:
    """Con semilla fija, repetir una prueba devolvía la MISMA imagen.

    Le pasó al usuario: el modelo se inventó un cordón colgando del cuello, y
    volver a probar daba el mismo cordón. Cada prueba lleva ahora su semilla.
    """
    ModeloQueInventa.variantes = []
    cuerpo = {"person_photo_id": foto["id"], "garment_upload_id": uploaded_garment["id"]}
    primera = auth_client.post("/api/try-ons", json=cuerpo).json()
    segunda = auth_client.post("/api/try-ons", json=cuerpo).json()

    assert len(ModeloQueInventa.variantes) == 2
    assert ModeloQueInventa.variantes[0] != ModeloQueInventa.variantes[1]
    assert ModeloQueInventa.variantes == [primera["id"], segunda["id"]]


# --- Lo medido el 10/11/2026 con salidas reales del modelo --------------------------


def _prenda_roja() -> Image.Image:
    """La prenda como se le manda al modelo: sobre blanco, con algo de sombra."""
    px = np.full((96, 96, 3), 255, dtype=np.uint8)
    sombra = np.linspace(1.0, 0.75, 64)[:, None, None]
    px[16:80, 16:80] = (np.array(PRENDA_NUEVA) * sombra).astype(np.uint8)
    return Image.fromarray(px)


def test_la_ropa_que_el_modelo_se_inventa_no_tapa_la_piel() -> None:
    """Las mangas largas verdes bajo una camiseta roja de manga corta.

    Pasó con la semilla 66, en los dos modos del modelo y con 30 y con 50
    pasos. Para el analizador eran ropa, y entraban encima de los brazos.
    No tienen ningún color de la prenda: donde tapaban piel, vuelve la foto.
    """
    alto, ancho = 240, 240
    persona = np.full((alto, ancho, 3), 200, dtype=np.float32)
    antes = np.full((alto, ancho), P.FONDO, dtype=np.uint8)
    persona[60:160, 80:160] = 30  # la camiseta negra que lleva
    antes[60:160, 80:160] = P.ROPA_ARRIBA
    persona[90:200, 40:80] = PIEL  # el brazo, al aire
    antes[90:200, 40:80] = P.BRAZO_IZQ

    generada, despues = persona.copy(), antes.copy()
    generada[60:160, 80:160] = PRENDA_NUEVA  # la camiseta roja, bien puesta
    generada[90:200, 40:80] = (20, 110, 70)  # y la manga verde que nadie pidió
    despues[90:200, 40:80] = P.ROPA_ARRIBA

    sin_paleta = zona_editable(persona, generada, antes, despues, GarmentCategory.TOP)
    assert sin_paleta.alfa[150, 60] == 1.0, "sin saber los colores de la prenda, la manga pasa"

    zona = zona_editable(
        persona, generada, antes, despues, GarmentCategory.TOP, paleta=paleta_de(_prenda_roja())
    )
    assert zona.alfa[110, 120] == 1.0, "la prenda de verdad se toma"
    assert zona.alfa[150, 60] == 0.0, "la manga inventada no: ahí sigue el brazo de la foto"
    assert zona.inventado > 0.05
    assert "otra variante" in V._aviso(0.0, zona.inventado)


def test_si_toda_la_prenda_sale_de_otro_color_no_se_le_quita_nada() -> None:
    """La salvaguarda: «inventado» en más de media prenda es otra luz, no una manga."""
    alto, ancho = 240, 240
    persona = np.full((alto, ancho, 3), 200, dtype=np.float32)
    antes = np.full((alto, ancho), P.FONDO, dtype=np.uint8)
    persona[90:200, 40:80] = PIEL
    antes[90:200, 40:80] = P.BRAZO_IZQ
    generada, despues = persona.copy(), antes.copy()
    generada[60:200, 40:160] = (20, 110, 70)  # manga larga, y toda de otro color
    despues[60:200, 40:160] = P.ROPA_ARRIBA

    zona = zona_editable(
        persona, generada, antes, despues, GarmentCategory.TOP, paleta=paleta_de(_prenda_roja())
    )
    assert zona.alfa[150, 60] == 1.0
    assert zona.inventado == 0.0


def test_donde_asoma_el_fondo_se_pone_el_de_la_foto_no_el_del_modelo() -> None:
    """El «fantasma» claro junto al hombro, y el ribete claro de la prenda.

    La prenda vieja es más ancha que la nueva, y el modelo regenera el fondo
    con otro color. Lo que asoma a los lados tiene que ser el fondo de la
    FOTO, con sus franjas, y el canto de la prenda no puede traerse una tira
    del fondo del modelo.
    """
    alto, ancho = 400, 300
    cielo, campo, del_modelo = (180, 200, 220), (90, 140, 80), (245, 245, 245)
    foto = np.zeros((alto, ancho, 3), dtype=np.uint8)
    foto[:200] = cielo
    foto[200:] = campo
    foto[100:300, 60:240] = CAMISA  # ancha
    generada = np.full((alto, ancho, 3), del_modelo, dtype=np.uint8)
    generada[100:300, 100:200] = PRENDA_NUEVA  # más estrecha

    compuesta = V.componer(
        Image.fromarray(foto),
        Image.fromarray(generada),
        _prenda_roja(),
        GarmentCategory.TOP,
        _etiquetar_por_color,
    )
    salida = np.asarray(compuesta.imagen, dtype=np.int32)

    assert np.abs(salida[200, 150] - np.array(PRENDA_NUEVA)).sum() < 30, "la prenda nueva está"
    for fila, franja in ((150, cielo), (250, campo)):
        for columna in (80, 220):  # donde estaba la camisa vieja y ya no hay prenda
            pixel = salida[fila, columna]
            assert np.abs(pixel - np.array(franja)).sum() < 60, (fila, columna, pixel.tolist())
    # Pegado al canto de la prenda, por fuera: ni rastro del fondo del modelo.
    assert np.abs(salida[150, 96] - np.array(cielo)).sum() < 60
    assert np.abs(salida[150, 204] - np.array(cielo)).sum() < 60
    # Y lejos de la persona la foto no se toca.
    assert np.abs(salida[20:80, :40] - foto[20:80, :40].astype(np.int32)).max() <= 1


def test_lo_que_la_persona_sostiene_no_es_fondo() -> None:
    """El móvil delante del pecho sale como «fondo», y no lo es.

    Con el vestido de noche, el relleno tomó el dorado del móvil y el negro
    de su cámara por colores de la pared y los arrastró hasta los hombros.
    Lo encerrado en la figura es figura, aunque lo una al exterior un pasillo
    estrecho; una bahía ancha —entre el brazo y el cuerpo— sí es fondo.
    """
    figura = np.zeros((200, 200), dtype=bool)
    figura[40:160, 60:140] = True
    figura[80:110, 90:110] = False  # el móvil
    figura[40:80, 97:103] = False  # el pasillo entre el pelo y el hombro, hasta fuera
    figura[110:160, 0:60] = True  # un brazo...
    figura[110:150, 0:50] = False  # ...que encierra fondo de verdad, abierto por un lado

    solida = _solida(figura, 200)
    assert solida[95, 100], "el hueco del móvil es figura"
    assert not solida[130, 20], "lo que se abre de par en par al exterior es fondo"
    assert not solida[10, 10]


def test_una_prenda_de_arriba_se_encuadra_sin_las_piernas() -> None:
    """Los píxeles del modelo, para lo que se prueba.

    En una foto de cuerpo entero la persona ocupaba 193 de los 576 px de
    ancho del modelo; encuadrando de la cabeza a medio muslo, 318.
    """
    etiquetas = np.full((400, 300), P.FONDO, dtype=np.uint8)
    etiquetas[40:90, 130:170] = P.CARA
    etiquetas[90:200, 110:190] = P.ROPA_ARRIBA
    etiquetas[200:300, 115:185] = P.PANTALON
    etiquetas[300:380, 120:180] = P.PIERNA_IZQ
    tamano = (600, 800)

    entera = V._encuadre_por_categoria(etiquetas, 2.0, tamano, GarmentCategory.FULL)
    arriba = V._encuadre_por_categoria(etiquetas, 2.0, tamano, GarmentCategory.TOP)
    assert entera == V._encuadre(etiquetas != P.FONDO, 2.0, tamano)
    assert arriba[1] <= 2 * 40, "entra la cabeza"
    assert arriba[3] >= 2 * 200, "y toda la prenda que lleva puesta"
    assert arriba[3] < 2 * 300, "pero no las piernas"
    assert (arriba[3] - arriba[1]) < 0.75 * (entera[3] - entera[1])
    assert abs((arriba[2] - arriba[0]) / (arriba[3] - arriba[1]) - V.PROPORCION) < 0.01

    # Sin nada que el analizador reconozca como prenda de arriba, no hay por
    # dónde cortar: el cuerpo entero.
    etiquetas[etiquetas == P.ROPA_ARRIBA] = P.BRAZO_IZQ
    assert V._encuadre_por_categoria(etiquetas, 2.0, tamano, GarmentCategory.TOP) == entera


def test_la_prenda_que_llega_al_pie_del_cuadro_se_avisa() -> None:
    """Un abrigo probado como «parte de arriba» quedaría cortado en recto."""
    assert V._aviso(0.0) is None
    aviso = V._aviso(0.0, cortada=True)
    assert "Vestido o mono" in aviso
    todo = V._aviso(0.05, inventado=0.02, cortada=True)
    assert "otra variante" in todo and "Vestido o mono" in todo and "fuera de la prenda" in todo


def test_la_prueba_guarda_lo_que_devolvio_el_modelo(
    auth_client: TestClient, foto: dict, uploaded_garment: dict, storage, db_session, modelo_falso
) -> None:
    """La salida cruda y su caja: con ellas se recompone sin gastar cuota.

    Hasta el 10/11/2026 solo se guardaba el resultado compuesto, y medir un
    cambio de `conservar.py` exigía repetir la prueba con Hugging Face.
    """
    creada = auth_client.post(
        "/api/try-ons",
        json={
            "person_photo_id": foto["id"],
            "garment_upload_id": uploaded_garment["id"],
            "category": "top",
        },
    ).json()
    prueba = auth_client.get(f"/api/try-ons/{creada['id']}").json()
    assert prueba["status"] == "completed", prueba["error_message"]
    assert not any("raw" in campo for campo in prueba), "la salida cruda no se publica"

    fila = db_session.get(TryOn, creada["id"])
    db_session.refresh(fila)
    assert fila.raw_output_key and fila.raw_box
    caja = tuple(int(v) for v in fila.raw_box.split(","))
    cruda = Image.open(io.BytesIO(storage.read(fila.raw_output_key)))
    # El doble de prueba devuelve el cuadro a la mitad de tamaño.
    assert cruda.size == ((caja[2] - caja[0]) // 2, (caja[3] - caja[1]) // 2)

    def abrir(url: str) -> Image.Image:
        return Image.open(io.BytesIO(storage.read(url.split("/media/")[1])))

    otra_vez = recomponer(
        abrir(prueba["person_image_url"]),
        caja,
        cruda,
        abrir(prueba["garment_image_url"]),
        GarmentCategory.TOP,
        proveedor="doble-de-prueba",
        etiquetar=_etiquetar_por_color,
    )
    guardada = np.asarray(abrir(prueba["output_image_url"]).convert("RGB"), dtype=np.int32)
    assert np.abs(np.asarray(otra_vez.imagen, dtype=np.int32) - guardada).mean() < 2

    clave = fila.raw_output_key
    assert auth_client.delete(f"/api/try-ons/{creada['id']}").status_code == 200
    with pytest.raises(FileNotFoundError):
        storage.read(clave)


def test_al_modelo_no_se_le_pide_borrar_la_prenda_vieja_y_se_le_dan_50_pasos(
    monkeypatch, tmp_path
) -> None:
    """Borrando, un vestido largo salió como minivestido; a 30 pasos, agujereado."""
    from app.probador import fashn
    from app.probador.proveedor import PeticionDePrueba

    llamadas: list[dict] = []

    class Trabajo:
        def result(self, timeout=None):
            return {"path": "resultado"}

    class Cliente:
        def submit(self, **argumentos):
            llamadas.append(argumentos)
            return Trabajo()

    ruta = tmp_path / "salida.png"
    Image.new("RGB", (20, 30), (1, 2, 3)).save(ruta)
    monkeypatch.setattr(fashn, "_conectar", lambda _cliente: Cliente())
    monkeypatch.setattr(fashn, "_descargar", lambda *_: ruta)

    peticion = PeticionDePrueba(
        persona=Image.new("RGB", (20, 30)),
        prenda=Image.new("RGB", (20, 30)),
        categoria=GarmentCategory.FULL,
        variante=25,
    )
    modelo = fashn.ModeloFashn()
    assert modelo.vestir(peticion).size == (20, 30)
    assert llamadas[0]["segmentation_free"] is True
    assert llamadas[0]["num_timesteps"] == 50
    assert llamadas[0]["seed"] == 42 + 25
    assert modelo.parametros(peticion) == "steps=50;guidance=1.5;seed=67;erase=0;photo=flat-lay"

    # Y se puede volver al modo de borrar sin tocar código.
    monkeypatch.setattr(settings, "VTO_ERASE_FIRST", True)
    modelo.vestir(peticion)
    assert llamadas[1]["segmentation_free"] is False


# --- Lo medido el 12/11/2026: el modelo dibuja a la persona más delgada ------------------


def _hombre_de_brazo_grueso():
    """Foto: camiseta de manga corta y un brazo grueso al lado. Devuelve imagen y etiquetas."""
    alto, ancho = 240, 240
    persona = np.full((alto, ancho, 3), 200, dtype=np.float32)
    partes = np.full((alto, ancho), P.FONDO, dtype=np.uint8)
    persona[40:200, 100:180] = 30  # el cuerpo de la camiseta
    partes[40:200, 100:180] = P.ROPA_ARRIBA
    persona[40:90, 40:100] = 30  # la manga corta, sobre el brazo
    partes[40:90, 40:100] = P.ROPA_ARRIBA
    persona[90:220, 40:100] = PIEL  # el brazo, grueso, al aire desde la manga
    partes[90:220, 40:100] = P.BRAZO_IZQ
    return persona, partes


def test_el_brazo_que_el_modelo_deja_al_aire_conserva_su_ancho() -> None:
    """La camiseta que se comía medio antebrazo (prueba 30).

    El modelo dibuja el brazo más fino, con el borde de fuera en su sitio, y
    el hueco que deja por dentro lo ocupa la camiseta. Como eso «es ropa»,
    entraba encima del brazo de la foto y parecía que la persona había
    perdido masa muscular. Donde el modelo enseña el brazo, el brazo de la
    foto se queda entero; por encima del dobladillo, entra la manga.
    """
    persona, antes = _hombre_de_brazo_grueso()
    generada, despues = persona.copy(), np.full(antes.shape, P.FONDO, dtype=np.uint8)
    generada[40:200, 100:180] = PRENDA_NUEVA
    despues[40:200, 100:180] = P.ROPA_ARRIBA
    generada[40:120, 40:100] = PRENDA_NUEVA  # la manga nueva, más larga que la vieja
    despues[40:120, 40:100] = P.ROPA_ARRIBA
    generada[120:220, 40:70] = PIEL  # el brazo que dibuja el modelo: la mitad de ancho
    despues[120:220, 40:70] = P.BRAZO_IZQ
    generada[120:200, 70:100] = PRENDA_NUEVA  # y la camiseta, en el sitio que deja libre
    despues[120:200, 70:100] = P.ROPA_ARRIBA

    zona = zona_editable(persona, generada, antes, despues, GarmentCategory.TOP)
    assert zona.alfa[170, 85] == 0.0, "el antebrazo de la foto se queda entero"
    assert zona.alfa[170, 55] == 0.0, "y donde es brazo en las dos, como siempre"
    assert zona.alfa[105, 70] == 1.0, "por encima del dobladillo entra la manga nueva"
    assert zona.alfa[120, 140] == 1.0, "y el cuerpo de la camiseta"
    assert zona.brazo_devuelto > 0.02


def test_una_manga_larga_si_tapa_el_brazo() -> None:
    """La regla del brazo no puede borrar una manga.

    De una chaqueta de manga larga solo asoma la mano, que no tiene dirección
    propia: el tramo se mide entonces sobre el brazo de la foto. Con el eje de
    la mano, o sin cortar por dónde acaba, volvía el brazo entero de la foto.
    """
    persona, antes = _hombre_de_brazo_grueso()
    generada, despues = persona.copy(), np.full(antes.shape, P.FONDO, dtype=np.uint8)
    generada[40:200, 100:180] = PRENDA_NUEVA
    despues[40:200, 100:180] = P.ROPA_ARRIBA
    generada[40:190, 40:100] = PRENDA_NUEVA  # la manga llega a la muñeca
    despues[40:190, 40:100] = P.ROPA_ARRIBA
    generada[190:220, 50:90] = PIEL  # solo asoma la mano
    despues[190:220, 50:90] = P.BRAZO_IZQ

    zona = zona_editable(persona, generada, antes, despues, GarmentCategory.TOP)
    assert zona.alfa[140, 70] == 1.0, "la manga tapa el brazo"
    assert zona.alfa[100, 95] == 1.0
    assert zona.alfa[205, 70] == 0.0, "la mano es la de la foto"
    assert zona.brazo_devuelto < 0.005
