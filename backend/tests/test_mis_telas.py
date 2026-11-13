"""Las telas del propio taller: Ep6-Hu7 a Ep6-Hu11.

Cada prueba lleva en su nombre el criterio de aceptación que fija. Las fotos
son sintéticas pero de verdad: una lisa con grano, una raya y un estampado de
manchas, del tamaño de una foto de móvil reducida.
"""

import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageFilter

from app.textil import tela_propia
from tests.conftest import auth_headers, make_prenda_bytes, register_and_login

# --- Fotos de tela sintéticas ------------------------------------------------


def _png(px: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(np.clip(px, 0, 255).astype(np.uint8), mode="RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def foto_lisa(lado: int = 700, color=(150, 40, 50)) -> bytes:
    ruido = np.random.default_rng(3).normal(0, 4, (lado, lado, 1))
    return _png(np.array(color, dtype=np.float32)[None, None, :] + ruido)


def foto_rayas(lado: int = 700, ancho: int = 35, horizontales: bool = False) -> bytes:
    eje = np.arange(lado)
    franja = (eje // ancho) % 2 == 0
    oscuro, claro = np.array([30, 45, 140.0]), np.array([236, 236, 232.0])
    fila = np.where(franja[:, None], oscuro, claro)
    px = np.broadcast_to(fila[None, :, :], (lado, lado, 3)).copy()
    if horizontales:
        px = px.transpose(1, 0, 2)
    return _png(px)


def foto_estampada(lado: int = 700, desenfoque: float = 0.0) -> bytes:
    rng = np.random.default_rng(5)
    imagen = Image.new("RGB", (lado, lado), (225, 215, 195))
    px = np.asarray(imagen, dtype=np.float32).copy()
    yy, xx = np.mgrid[0:lado, 0:lado]
    for _ in range(60):
        cx, cy, r = rng.integers(0, lado), rng.integers(0, lado), rng.integers(8, 30)
        dentro = (xx - cx) ** 2 + (yy - cy) ** 2 < r * r
        px[dentro] = rng.integers(40, 200, 3)
    imagen = Image.fromarray(px.astype(np.uint8), mode="RGB")
    if desenfoque:
        imagen = imagen.filter(ImageFilter.GaussianBlur(desenfoque))
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    return buffer.getvalue()


def _subir(client: TestClient, nombre: str, foto: bytes, tipo: str = "solid", **extra) -> dict:
    respuesta = client.post(
        "/api/my-fabrics",
        data={"name": nombre, "pattern": tipo, **{k: str(v) for k, v in extra.items()}},
        files={"file": ("tela.png", foto, "image/png")},
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


# --- Ep6-Hu7: añadir mi propia tela desde una foto ---------------------------


def test_hu7_se_anade_una_tela_con_nombre_y_foto(auth_client: TestClient) -> None:
    tela = _subir(auth_client, "Paño granate del taller", foto_lisa(), composition="Lana")
    assert tela["name"] == "Paño granate del taller"
    assert tela["own"] is True
    assert tela["composition"] == "Lana"
    assert tela["photo_url"] and tela["texture_url"], "guarda la foto y el mosaico"
    assert tela["pattern"] == "solid"


def test_hu7_la_tela_nueva_se_puede_elegir_al_probar_una_prenda(
    auth_client: TestClient, uploaded_garment: dict
) -> None:
    tela = _subir(auth_client, "Raya marinera propia", foto_rayas(), "stripes")
    assert tela["id"] in [t["id"] for t in auth_client.get("/api/my-fabrics").json()]

    respuesta = auth_client.post(
        "/api/trials", json={"garment_upload_id": uploaded_garment["id"], "fabric_id": tela["id"]}
    )
    assert respuesta.status_code == 202, respuesta.text
    prueba = auth_client.get(f"/api/trials/{respuesta.json()['id']}").json()
    assert prueba["status"] == "completed", prueba["error_message"]


def test_hu7_no_cuesta_dinero(auth_client: TestClient, monkeypatch) -> None:
    """Ningún camino de la tela propia llama al cliente de OpenAI."""
    import app.textil.tejido_ia as tejido_ia

    def prohibido(*_a, **_k):  # pragma: no cover - si se llama, la prueba falla
        raise AssertionError("la tela propia no debe llamar a la IA generativa")

    monkeypatch.setattr(tejido_ia, "sintetizar_mosaico", prohibido)
    monkeypatch.setattr(tejido_ia, "reconstruir_estampado", prohibido)
    for tipo, foto in (("solid", foto_lisa()), ("stripes", foto_rayas()), ("print", foto_estampada())):
        _subir(auth_client, f"Sin coste {tipo}", foto, tipo)


def test_hu7_no_se_repite_el_nombre_dentro_del_mismo_taller(auth_client: TestClient) -> None:
    _subir(auth_client, "Lino crudo", foto_lisa())
    otra = auth_client.post(
        "/api/my-fabrics",
        data={"name": "Lino crudo", "pattern": "solid"},
        files={"file": ("t.png", foto_lisa(), "image/png")},
    )
    assert otra.status_code == 409


def test_hu7_un_archivo_que_no_es_imagen_se_rechaza(auth_client: TestClient) -> None:
    respuesta = auth_client.post(
        "/api/my-fabrics",
        data={"name": "Falsa", "pattern": "solid"},
        files={"file": ("t.png", b"esto no es una imagen", "image/png")},
    )
    assert respuesta.status_code == 422


# --- Ep6-Hu8: que mis telas sean solo mías -----------------------------------


def test_hu8_la_pantalla_de_telas_separa_catalogo_y_mias(auth_client: TestClient) -> None:
    mia = _subir(auth_client, "Solo mía", foto_lisa())
    catalogo = [t["id"] for t in auth_client.get("/api/fabrics").json()]
    assert mia["id"] not in catalogo, "una tela de taller no sale en el escaparate"
    assert [t["id"] for t in auth_client.get("/api/my-fabrics").json()] == [mia["id"]]


def test_hu8_la_tela_de_otro_responde_404(client: TestClient, user_token) -> None:
    _, token = user_token
    _, token_otro = register_and_login(client, email="otro-taller@example.com")
    ajena = client.post(
        "/api/my-fabrics",
        data={"name": "Del otro taller", "pattern": "solid"},
        files={"file": ("t.png", foto_lisa(), "image/png")},
        headers=auth_headers(token_otro),
    ).json()

    yo = auth_headers(token)
    assert client.get(f"/api/my-fabrics/{ajena['id']}", headers=yo).status_code == 404
    assert client.patch(f"/api/my-fabrics/{ajena['id']}", json={"name": "x"}, headers=yo).status_code == 404
    assert client.delete(f"/api/my-fabrics/{ajena['id']}", headers=yo).status_code == 404
    # Tampoco por el catálogo, ni con token ni sin él.
    assert client.get(f"/api/fabrics/{ajena['id']}", headers=yo).status_code == 404
    assert client.get(f"/api/fabrics/{ajena['id']}").status_code == 404
    assert ajena["id"] not in [t["id"] for t in client.get("/api/my-fabrics", headers=yo).json()]


def test_hu8_no_se_puede_probar_una_prenda_con_la_tela_de_otro(client: TestClient, user_token) -> None:
    _, token = user_token
    _, token_otro = register_and_login(client, email="otro-taller-2@example.com")
    ajena = client.post(
        "/api/my-fabrics",
        data={"name": "Ajena", "pattern": "solid"},
        files={"file": ("t.png", foto_lisa(), "image/png")},
        headers=auth_headers(token_otro),
    ).json()
    prenda = client.post(
        "/api/garment-uploads",
        data={"name": "Mía", "kind": "photo"},
        files={"file": ("p.png", make_prenda_bytes(), "image/png")},
        headers=auth_headers(token),
    ).json()

    respuesta = client.post(
        "/api/trials",
        json={"garment_upload_id": prenda["id"], "fabric_id": ajena["id"]},
        headers=auth_headers(token),
    )
    assert respuesta.status_code == 404


def test_hu8_el_catalogo_sigue_siendo_publico_en_lectura(client: TestClient) -> None:
    assert client.get("/api/fabrics").status_code == 200
    assert client.get("/api/my-fabrics").status_code == 401


# --- Ep6-Hu9: convertir la foto en un mosaico que se repite -----------------


@pytest.mark.parametrize(
    ("tipo", "foto"),
    [
        ("solid", foto_lisa()),
        ("stripes", foto_rayas()),
        ("stripes", foto_rayas(horizontales=True)),
        ("print", foto_estampada()),
    ],
    ids=["lisa", "rayas", "rayas-horizontales", "estampada"],
)
def test_hu9_el_mosaico_se_calcula_solo_y_se_repite_sin_junta(
    auth_client: TestClient, tipo: str, foto: bytes
) -> None:
    respuesta = auth_client.post(
        "/api/my-fabrics/preview",
        data={"pattern": tipo},
        files={"file": ("t.png", foto, "image/png")},
    )
    assert respuesta.status_code == 200, respuesta.text
    vista = respuesta.json()
    assert vista["mosaic_data_url"].startswith("data:image/jpeg;base64,")
    assert vista["seam"] < vista["seam_limit"], f"junta {vista['seam']}"
    assert vista["seam_visible"] is False


def test_hu9_la_vista_previa_no_guarda_nada(auth_client: TestClient) -> None:
    auth_client.post(
        "/api/my-fabrics/preview",
        data={"pattern": "solid"},
        files={"file": ("t.png", foto_lisa(), "image/png")},
    )
    assert auth_client.get("/api/my-fabrics").json() == []


def test_hu9_una_raya_sale_vertical_aunque_la_foto_sea_horizontal() -> None:
    """La raya se coloca en vertical en el mosaico; la veta la gira en cada pieza."""
    hecha = tela_propia.digitalizar(Image.open(io.BytesIO(foto_rayas(horizontales=True))), "stripes")
    px = np.asarray(hecha.mosaico.convert("L"), dtype=np.float32)
    assert px.mean(axis=0).std() > 5 * px.mean(axis=1).std()


def test_hu9_una_lisa_no_tiene_rayas_que_medir(auth_client: TestClient) -> None:
    respuesta = auth_client.post(
        "/api/my-fabrics/preview",
        data={"pattern": "stripes"},
        files={"file": ("t.png", foto_lisa(), "image/png")},
    )
    assert respuesta.status_code == 422
    assert "estampada" in respuesta.json()["detail"], "dice qué elegir en su lugar"


def test_hu9_se_puede_ajustar_la_repeticion(auth_client: TestClient) -> None:
    tela = _subir(auth_client, "Estampado propio", foto_estampada(), "print", default_repeat=3)
    assert tela["default_repeat"] == 3


# --- Ep6-Hu10: avisar si la foto de la tela no sirve ------------------------


def _avisos(client: TestClient, foto: bytes, tipo: str = "print") -> list[str]:
    respuesta = client.post(
        "/api/my-fabrics/preview", data={"pattern": tipo}, files={"file": ("t.png", foto, "image/png")}
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()["warnings"]


def test_hu10_una_foto_buena_no_tiene_avisos(auth_client: TestClient) -> None:
    assert _avisos(auth_client, foto_estampada()) == []


def test_hu10_avisa_si_es_pequena(auth_client: TestClient) -> None:
    avisos = _avisos(auth_client, foto_estampada(lado=400))
    assert any("pequeña" in a for a in avisos)


def test_hu10_avisa_si_esta_desenfocada(auth_client: TestClient) -> None:
    avisos = _avisos(auth_client, foto_estampada(desenfoque=3))
    assert any("desenfocada" in a for a in avisos)
    assert any("enfocar" in a for a in avisos), "dice cómo hacer la foto"


def test_hu10_avisa_si_la_luz_es_desigual(auth_client: TestClient) -> None:
    px = np.asarray(Image.open(io.BytesIO(foto_estampada())), dtype=np.float32)
    rampa = np.linspace(1.0, 1 / 1.8, px.shape[1])[None, :, None]
    avisos = _avisos(auth_client, _png(px * rampa))
    assert any("luz" in a for a in avisos)
    assert any("ventana" in a for a in avisos), "dice cómo hacer la foto"


def test_hu10_en_una_lisa_no_se_avisa_de_desenfoque(auth_client: TestClient) -> None:
    """De una lisa solo se toma el color, que no cambia por estar desenfocada."""
    assert _avisos(auth_client, foto_lisa(), "solid") == []


def test_hu10_una_foto_diminuta_no_se_intenta(auth_client: TestClient) -> None:
    respuesta = auth_client.post(
        "/api/my-fabrics/preview",
        data={"pattern": "solid"},
        files={"file": ("t.png", foto_lisa(lado=80), "image/png")},
    )
    assert respuesta.status_code == 422


# --- Ep6-Hu11: editar y borrar mis telas ------------------------------------


def test_hu11_se_editan_nombre_composicion_y_repeticion(auth_client: TestClient) -> None:
    tela = _subir(auth_client, "Borrador", foto_lisa())
    respuesta = auth_client.patch(
        f"/api/my-fabrics/{tela['id']}",
        json={"name": "Paño definitivo", "composition": "80% lana, 20% poliamida", "default_repeat": 9},
    )
    assert respuesta.status_code == 200, respuesta.text
    editada = respuesta.json()
    assert (editada["name"], editada["composition"], editada["default_repeat"]) == (
        "Paño definitivo",
        "80% lana, 20% poliamida",
        9,
    )


def test_hu11_borrar_una_tela_sin_pruebas_la_quita_del_todo(auth_client: TestClient) -> None:
    tela = _subir(auth_client, "Para borrar", foto_lisa())
    assert auth_client.delete(f"/api/my-fabrics/{tela['id']}").status_code == 204
    assert auth_client.get(f"/api/my-fabrics/{tela['id']}").status_code == 404
    assert auth_client.get("/api/my-fabrics?include_retired=true").json() == []


def test_hu11_borrar_una_tela_conserva_sus_pruebas(
    auth_client: TestClient, uploaded_garment: dict
) -> None:
    tela = _subir(auth_client, "Con pruebas", foto_lisa())
    prueba = auth_client.post(
        "/api/trials", json={"garment_upload_id": uploaded_garment["id"], "fabric_id": tela["id"]}
    ).json()

    assert auth_client.delete(f"/api/my-fabrics/{tela['id']}").status_code == 204

    conservada = auth_client.get(f"/api/trials/{prueba['id']}")
    assert conservada.status_code == 200
    assert conservada.json()["output_image_url"] is not None
    # Ya no sale para elegir, pero el historial sigue sabiendo su nombre.
    assert auth_client.get("/api/my-fabrics").json() == []
    retiradas = auth_client.get("/api/my-fabrics?include_retired=true").json()
    assert [t["name"] for t in retiradas] == ["Con pruebas"]
    # Y no se puede probar con ella otra vez.
    otra = auth_client.post(
        "/api/trials", json={"garment_upload_id": uploaded_garment["id"], "fabric_id": tela["id"]}
    )
    assert otra.status_code == 404


def test_hu11_las_telas_del_catalogo_no_se_editan_ni_borran_como_mias(
    auth_client: TestClient, fabric_with_texture: dict
) -> None:
    fid = fabric_with_texture["id"]
    assert auth_client.patch(f"/api/my-fabrics/{fid}", json={"name": "Robada"}).status_code == 404
    assert auth_client.delete(f"/api/my-fabrics/{fid}").status_code == 404
    assert auth_client.get(f"/api/fabrics/{fid}").json()["name"] == "Lino de prueba"


def test_hu11_una_tela_mia_no_se_toca_por_el_camino_del_catalogo(auth_client: TestClient) -> None:
    tela = _subir(auth_client, "Mía de verdad", foto_lisa())
    assert auth_client.patch(f"/api/fabrics/{tela['id']}", json={"active": False}).status_code == 404
