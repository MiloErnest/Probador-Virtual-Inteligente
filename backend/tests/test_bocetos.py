"""Del boceto a la prenda: el único camino donde la IA inventa.

Lo que estas pruebas sostienen es el reparto: la IA genera la prenda UNA vez
por boceto, y las telas se prueban después sobre ella con el motor
determinista, gratis. Ninguna llama a OpenAI: `conftest.sin_gastar_dinero` lo
impide, y el modelo se sustituye por `GeneradorFalso`.
"""

from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import settings
from app.textil import boceto_ia
from app.textil.segmentar import segmentar_prenda
from tests.conftest import (
    GeneradorFalso,
    auth_headers,
    make_boceto_bytes,
    make_prenda_bytes,
    register_and_login,
)


def subir_boceto(cliente: TestClient, nombre: str = "Vestido") -> dict:
    respuesta = cliente.post(
        "/api/garment-uploads",
        data={"name": nombre, "kind": "sketch"},
        files={"file": ("boceto.png", make_boceto_bytes(), "image/png")},
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def clave_de(url: str) -> str:
    return url.split("/media/")[1]


# --- El camino ---------------------------------------------------------------


def test_un_boceto_se_convierte_en_prenda(
    auth_client: TestClient, generador_de_bocetos: GeneradorFalso
) -> None:
    """Sube en `pending` y acaba en `ready` con la prenda, su recorte y su dibujo."""
    subido = subir_boceto(auth_client)
    assert subido["status"] == "pending"
    # Mientras no hay prenda, la imagen es el propio dibujo.
    assert subido["image_url"] == subido["sketch_url"]

    prenda = auth_client.get(f"/api/garment-uploads/{subido['id']}").json()
    assert prenda["status"] == "ready", prenda["error_message"]
    assert prenda["kind"] == "sketch"
    assert prenda["image_url"] != prenda["sketch_url"]
    assert prenda["sketch_url"] == subido["sketch_url"]
    assert prenda["mask_url"] is not None
    assert (prenda["width"], prenda["height"]) == (600, 800)
    assert prenda["tokens_used"] == 1234
    assert generador_de_bocetos.llamadas == 1


def test_las_telas_se_prueban_sobre_la_prenda_sin_volver_a_la_ia(
    auth_client: TestClient, generador_de_bocetos: GeneradorFalso, fabric_with_texture: dict
) -> None:
    """La IA, una vez por boceto. Cada tela después es determinista y gratis.

    Es lo que hace que comparar signifique algo: entre dos pruebas de la misma
    prenda lo único que cambia es la tela.
    """
    boceto = subir_boceto(auth_client)

    for _ in range(2):
        creada = auth_client.post(
            "/api/trials",
            json={"garment_upload_id": boceto["id"], "fabric_id": fabric_with_texture["id"]},
        )
        assert creada.status_code == 202, creada.text
        prueba = auth_client.get(f"/api/trials/{creada.json()['id']}").json()
        assert prueba["status"] == "completed", prueba["error_message"]
        assert prueba["method"] == "retexture"
        assert prueba["provider"] == "retexturizado-local"
        assert prueba["tokens_used"] is None

    assert generador_de_bocetos.llamadas == 1


def test_sin_ia_configurada_el_boceto_falla_diciendo_que_hacer(
    auth_client: TestClient, fabric_with_texture: dict
) -> None:
    """No hay camino gratuito al que caer en silencio: sin IA, no hay prenda."""
    subido = subir_boceto(auth_client)

    prenda = auth_client.get(f"/api/garment-uploads/{subido['id']}").json()
    assert prenda["status"] == "failed"
    assert "AI_PROVIDER" in prenda["error_message"]

    # Y sobre un dibujo no se prueban telas.
    rechazada = auth_client.post(
        "/api/trials",
        json={"garment_upload_id": subido["id"], "fabric_id": fabric_with_texture["id"]},
    )
    assert rechazada.status_code == 422
    assert "prenda generada" in rechazada.json()["detail"]


def test_un_proveedor_desconocido_falla_en_voz_alta(
    auth_client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "AI_PROVIDER", "otro")
    subido = subir_boceto(auth_client)

    prenda = auth_client.get(f"/api/garment-uploads/{subido['id']}").json()
    assert prenda["status"] == "failed"
    assert "no se reconoce" in prenda["error_message"]


# --- Variantes ---------------------------------------------------------------


def test_otra_variante_es_una_prenda_nueva_y_no_pisa_la_anterior(
    auth_client: TestClient, generador_de_bocetos: GeneradorFalso
) -> None:
    """Las telas probadas sobre la primera siguen siendo de la primera."""
    primera = subir_boceto(auth_client)
    antes = auth_client.get(f"/api/garment-uploads/{primera['id']}").json()

    respuesta = auth_client.post(f"/api/garment-uploads/{primera['id']}/variants")
    assert respuesta.status_code == 202, respuesta.text
    segunda = respuesta.json()
    assert segunda["id"] != primera["id"]
    assert segunda["name"] == primera["name"]

    assert auth_client.get(f"/api/garment-uploads/{primera['id']}").json() == antes
    lista = auth_client.get(f"/api/garment-uploads/{segunda['id']}").json()
    assert lista["status"] == "ready"
    assert lista["image_url"] != antes["image_url"]
    assert generador_de_bocetos.llamadas == 2


def test_una_prenda_fallida_se_reintenta_en_la_misma_fila(
    auth_client: TestClient, monkeypatch
) -> None:
    """Reintentar no deja un rastro de prendas fallidas en el taller."""
    fallida = subir_boceto(auth_client)
    assert auth_client.get(f"/api/garment-uploads/{fallida['id']}").json()["status"] == "failed"

    monkeypatch.setattr(boceto_ia, "generador_configurado", lambda: GeneradorFalso())
    reintento = auth_client.post(f"/api/garment-uploads/{fallida['id']}/variants")
    assert reintento.status_code == 202, reintento.text
    assert reintento.json()["id"] == fallida["id"]

    prenda = auth_client.get(f"/api/garment-uploads/{fallida['id']}").json()
    assert prenda["status"] == "ready"
    assert prenda["error_message"] is None
    assert len(auth_client.get("/api/garment-uploads").json()) == 1


def test_una_fotografia_no_tiene_variantes(
    auth_client: TestClient, uploaded_garment: dict
) -> None:
    respuesta = auth_client.post(f"/api/garment-uploads/{uploaded_garment['id']}/variants")
    assert respuesta.status_code == 422


def test_la_variante_de_un_boceto_ajeno_responde_404(
    client: TestClient, generador_de_bocetos: GeneradorFalso
) -> None:
    """404 y no 403: el boceto de un taller es su trabajo, y un 403 lo confirma."""
    _, token_de_ana = register_and_login(client)
    boceto = client.post(
        "/api/garment-uploads",
        data={"name": "De Ana", "kind": "sketch"},
        files={"file": ("b.png", make_boceto_bytes(), "image/png")},
        headers=auth_headers(token_de_ana),
    ).json()

    _, token_de_luis = register_and_login(client, name="Luis", email="luis@example.com")
    respuesta = client.post(
        f"/api/garment-uploads/{boceto['id']}/variants", headers=auth_headers(token_de_luis)
    )
    assert respuesta.status_code == 404
    assert generador_de_bocetos.llamadas == 1


# --- Gasto -------------------------------------------------------------------


def test_los_bocetos_cuentan_para_el_techo_de_gasto(
    auth_client: TestClient, generador_de_bocetos: GeneradorFalso, monkeypatch
) -> None:
    """El techo se comprueba ANTES de generar: lo rechazado no cuesta nada."""
    monkeypatch.setattr(settings, "AI_TRIALS_PER_USER_PER_DAY", 2)
    primera = subir_boceto(auth_client)
    auth_client.post(f"/api/garment-uploads/{primera['id']}/variants")
    assert generador_de_bocetos.llamadas == 2

    tercera = auth_client.post(
        "/api/garment-uploads",
        data={"name": "Otro", "kind": "sketch"},
        files={"file": ("b.png", make_boceto_bytes(), "image/png")},
    )
    assert tercera.status_code == 422
    assert "límite" in tercera.json()["detail"]

    variante = auth_client.post(f"/api/garment-uploads/{primera['id']}/variants")
    assert variante.status_code == 422
    assert generador_de_bocetos.llamadas == 2

    # Una fotografía no gasta, y sigue pudiéndose subir.
    foto = auth_client.post(
        "/api/garment-uploads",
        data={"name": "Camisa", "kind": "photo"},
        files={"file": ("c.png", make_prenda_bytes(), "image/png")},
    )
    assert foto.status_code == 201


# --- Parecido con el dibujo --------------------------------------------------


def test_una_prenda_fiel_no_lleva_aviso(
    auth_client: TestClient, generador_de_bocetos: GeneradorFalso
) -> None:
    boceto = subir_boceto(auth_client)
    prenda = auth_client.get(f"/api/garment-uploads/{boceto['id']}").json()

    assert prenda["similarity"] > boceto_ia.PARECIDO_MINIMO
    assert prenda["similarity_warning"] is None


def test_si_la_ia_se_aparta_del_dibujo_se_avisa(auth_client: TestClient, monkeypatch) -> None:
    """El boceto es alto y estrecho; el modelo devuelve algo ancho y corto."""
    monkeypatch.setattr(
        boceto_ia, "generador_configurado", lambda: GeneradorFalso(caja=(0.05, 0.4, 0.95, 0.6))
    )
    boceto = subir_boceto(auth_client)
    prenda = auth_client.get(f"/api/garment-uploads/{boceto['id']}").json()

    assert prenda["status"] == "ready"
    assert prenda["similarity"] < boceto_ia.PARECIDO_MINIMO
    assert "otra variante" in prenda["similarity_warning"]


# --- Archivos ----------------------------------------------------------------


def test_borrar_un_boceto_borra_el_dibujo_la_prenda_y_el_recorte(
    auth_client: TestClient, generador_de_bocetos: GeneradorFalso, storage
) -> None:
    boceto = subir_boceto(auth_client)
    prenda = auth_client.get(f"/api/garment-uploads/{boceto['id']}").json()
    claves = [clave_de(prenda[campo]) for campo in ("image_url", "sketch_url", "mask_url")]
    for clave in claves:
        storage.read(clave)

    assert auth_client.delete(f"/api/garment-uploads/{boceto['id']}").status_code == 200

    for clave in claves:
        try:
            storage.read(clave)
        except FileNotFoundError:
            continue
        raise AssertionError(f"{clave} sigue en el almacén")


# --- El motor: medidas que fallaron de verdad --------------------------------


def _prenda_cruda_con_pliegues_en_sombra() -> Image.Image:
    """Una prenda en crudo sobre gris con dos pliegues hondos, cálidos y oscuros.

    Es lo que devolvió el modelo con el vestido de noche: la sombra de un
    pliegue en tela cruda tiene el croma de la piel.
    """
    from PIL import ImageDraw

    imagen = Image.new("RGB", (480, 640), (140, 140, 140))
    dibujo = ImageDraw.Draw(imagen)
    dibujo.rectangle((120, 100, 360, 560), fill=(236, 230, 214))
    for x in (190, 280):
        dibujo.rectangle((x, 240, x + 18, 520), fill=(150, 124, 92))
    return imagen


def test_los_pliegues_en_sombra_de_una_prenda_cruda_no_se_toman_por_piel() -> None:
    """El recorte de una prenda generada no busca figura.

    Con el vestido de noche, el paso que quita a la modelo de un figurín se
    llevó dos franjas de la cintura al bajo: las sombras cálidas de los
    pliegues. Se culpó primero al fondo gris, se cambió a azul, y salieron los
    mismos agujeros.
    """
    import numpy as np

    imagen = _prenda_cruda_con_pliegues_en_sombra()
    pliegue = (slice(260, 500), slice(193, 205))

    con_figura = np.asarray(segmentar_prenda(imagen).mascara)
    sin_figura = np.asarray(boceto_ia.recortar_prenda_generada(imagen).mascara)

    assert con_figura[pliegue].mean() < 64, "el caso ya no reproduce el fallo"
    assert sin_figura[pliegue].mean() > 250


def test_un_boceto_a_lapiz_va_en_crudo_y_uno_coloreado_conserva_su_color() -> None:
    """El sombreado gris no es el color de la prenda; un relleno de color, sí."""
    import io

    from PIL import ImageDraw

    a_lapiz = Image.open(io.BytesIO(make_boceto_bytes()))
    mascara = segmentar_prenda(a_lapiz, boceto=True).mascara
    assert boceto_ia.boceto_a_color(a_lapiz, mascara) is False

    coloreado = a_lapiz.copy()
    ImageDraw.Draw(coloreado).rectangle((66, 72, 234, 328), fill=(170, 40, 60))
    mascara = segmentar_prenda(coloreado, boceto=True).mascara
    assert boceto_ia.boceto_a_color(coloreado, mascara) is True


def test_la_misma_silueta_a_otro_tamano_y_en_otro_sitio_se_parece() -> None:
    """El modelo quita a la modelo y centra la prenda: no se compara píxel a píxel."""
    from PIL import ImageDraw

    def silueta(tamano, caja):
        lienzo = Image.new("L", tamano, 0)
        ImageDraw.Draw(lienzo).rectangle(caja, fill=255)
        return lienzo

    dibujo = silueta((300, 400), (60, 67, 240, 333))
    misma = silueta((1104, 1536), (402, 300, 942, 1098))
    otra = silueta((1104, 1536), (100, 600, 1000, 900))

    assert boceto_ia.parecido_de_silueta(dibujo, misma) > 0.95
    assert boceto_ia.parecido_de_silueta(dibujo, otra) < boceto_ia.PARECIDO_MINIMO
    # Un recorte vacío no se parece a nada, y no revienta.
    assert boceto_ia.parecido_de_silueta(dibujo, Image.new("L", (300, 400), 0)) == 0.0
