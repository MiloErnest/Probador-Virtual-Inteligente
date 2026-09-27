"""Pruebas del motor textil: las piezas que costó encontrar, fijadas.

La calidad de una imagen se juzga mirando, y eso está en PROJECT_STATUS.md. Lo
que se fija aquí son las PROPIEDADES que se midieron para llegar a cada pieza,
para que un cambio futuro no las rompa en silencio. Cada prueba es un caso que
falló de verdad antes de arreglarse.
"""

import numpy as np
from PIL import Image

from app.textil import digitalizar
from app.textil.bloqueo import bloquear_estructura
from app.textil.retexturizar import retexturizar
from app.textil.segmentar import _pegar_al_borde, _rellenar_desde_el_borde
from app.textil.tejido_ia import hacer_repetible, medir_junta, medir_periodo
from app.textil.veta import coordenadas_de_la_veta


def _vichy(lado: int = 256, cuadro: int = 32) -> Image.Image:
    eje = np.arange(lado)
    banda = ((eje // cuadro) % 2 == 0).astype(np.float32)
    rojo = np.maximum(banda[None, :], banda[:, None])
    px = np.stack([0.95 * np.ones_like(rojo), 1 - 0.7 * rojo, 1 - 0.7 * rojo], axis=-1)
    return Image.fromarray((px * 255).astype(np.uint8), mode="RGB")


# --- El relleno desde el borde ----------------------------------------------


def test_el_relleno_no_cruza_en_diagonal() -> None:
    """Vecindad de 4, como el recorrido en anchura que sustituye.

    Un recinto cerrado por píxeles que solo se tocan en diagonal tiene que
    seguir cerrado: si el relleno cruzara en diagonal, se colaría dentro de
    cualquier prenda cuyo contorno sea una escalera de un píxel.
    """
    similar = np.ones((7, 7), dtype=bool)
    for i in range(1, 6):
        similar[i, 1] = similar[i, 5] = similar[1, i] = similar[5, i] = False
    alcanzado = _rellenar_desde_el_borde(similar)
    assert alcanzado[0, 0]
    assert not alcanzado[3, 3], "el interior de un recinto cerrado no se alcanza"


# --- El filtro guiado: la causa del halo -------------------------------------


def test_el_borde_se_lleva_al_contorno_real_de_la_foto() -> None:
    """La máscara ampliada con el borde desplazado vuelve al borde real.

    Hacia fuera (el fondo que se colaba como prenda: el halo) y hacia dentro.
    Esta prueba desmintió la primera versión, que confiaba el trabajo al filtro
    guiado: con 6 px de error, el borde se quedaba a −5.
    """
    lado, alto = 2048, 256
    borde = lado // 2
    guia = np.full((alto, lado), 230, np.uint8)
    guia[:, borde:] = 40  # prenda oscura a la derecha
    for desplazamiento in (6, -6):
        mascara = np.zeros_like(guia)
        mascara[:, borde - desplazamiento:] = 255
        alfa = _pegar_al_borde(
            Image.fromarray(mascara), Image.fromarray(guia).convert("RGB"), (lado, alto)
        )
        fila = np.asarray(alfa, dtype=np.float32)[alto // 2] / 255.0
        primero = int(np.nonzero(fila > 0.5)[0].min())
        assert abs(primero - borde) <= 1, (desplazamiento, primero - borde)


# --- Cerrar la junta de un mosaico -------------------------------------------


def test_un_cuadro_se_cierra_sin_fantasmas() -> None:
    """Fundir a media anchura sin mirar el período dejaba el vichy fantasmal.

    El mosaico cerrado tiene que seguir siendo periódico con el mismo paso, y
    sin junta visible.
    """
    vichy = _vichy(lado=300, cuadro=37)  # período que NO divide al lado
    cerrado = hacer_repetible(vichy)
    px = np.asarray(cerrado, dtype=np.float32) / 255.0
    periodo = medir_periodo(px, 1)
    assert periodo is not None, "el cuadro sigue siendo un cuadro"
    assert medir_junta(cerrado) < 3.0


def test_una_tela_sin_periodo_tambien_se_cierra() -> None:
    ruido = np.random.default_rng(1).random((200, 200, 3)).astype(np.float32)
    lisa = Image.fromarray((ruido * 60 + 100).astype(np.uint8), mode="RGB")
    assert medir_junta(hacer_repetible(lisa)) < 3.0


# --- Digitalizar una raya ----------------------------------------------------


def test_una_raya_se_mide_con_su_proporcion_aunque_la_luz_cambie() -> None:
    """El umbral adaptativo por período: la luz del estante no lo engaña.

    Tres estimadores fallaron antes que este, uno de ellos daba 0,25 en una raya
    que es 50/50 y saltaba al mover el recorte cuatro píxeles.
    """
    ancho, alto, periodo = 600, 30, 40
    x = np.arange(ancho)
    oscuro = ((x % periodo) < periodo // 2).astype(np.float32)
    azul = np.array([0.12, 0.25, 0.75], dtype=np.float32)
    blanco = np.array([0.93, 0.93, 0.93], dtype=np.float32)
    fila = oscuro[:, None] * azul + (1 - oscuro[:, None]) * blanco
    # Luz de almacén: más oscuro a un lado y más en el lomo del rollo.
    luz = np.linspace(0.55, 1.0, ancho)[None, :, None] * np.linspace(0.8, 1.0, alto)[:, None, None]
    px = np.broadcast_to(fila[None], (alto, ancho, 3)) * luz
    rayas = Image.fromarray((px * 255).astype(np.uint8), mode="RGB")

    medida = digitalizar.medir_rayas(rayas)
    assert abs(medida["proporcion_oscuro"] - 0.5) < 0.06
    assert abs(medida["periodo_px"] - periodo) <= 1
    assert medida["oscuro"][2] > medida["oscuro"][0], "el color oscuro es el azul"


# --- La veta ------------------------------------------------------------------


def _camiseta(inclinacion_grados: float) -> np.ndarray:
    """Un torso rectangular con dos mangas que salen inclinadas."""
    alto, ancho = 400, 400
    alfa = np.zeros((alto, ancho), dtype=np.float32)
    alfa[120:380, 130:270] = 1.0
    yy, xx = np.mgrid[0:alto, 0:ancho]
    angulo = np.radians(inclinacion_grados)
    for lado in (-1, 1):
        # Eje de la manga: sale del hombro hacia fuera y hacia abajo.
        hombro = np.array([200 + lado * 60, 140])
        direccion = np.array([lado * np.sin(angulo), np.cos(angulo)])
        rel = np.stack([xx - hombro[0], yy - hombro[1]], axis=-1)
        a_lo_largo = rel @ direccion
        de_lado = np.abs(rel @ np.array([direccion[1], -direccion[0]]))
        alfa[(a_lo_largo > 0) & (a_lo_largo < 150) & (de_lado < 22)] = 1.0
    return alfa


def test_las_mangas_inclinadas_llevan_su_propia_veta() -> None:
    """Una raya corre a lo largo de la manga, no en vertical por la foto."""
    _, _, paneles = coordenadas_de_la_veta(_camiseta(inclinacion_grados=45))
    assert paneles == 2


def test_un_rectangulo_no_tiene_paneles() -> None:
    """Sin piezas estrechas no se gira nada: la veta del cuerpo es vertical.

    La primera versión, con el tensor de estructura, llenaba de «paneles» la
    zona junto a cualquier borde recto: el bajo de una camiseta salía con
    rayas horizontales.
    """
    alfa = np.zeros((300, 300), dtype=np.float32)
    alfa[40:260, 60:240] = 1.0
    _, _, paneles = coordenadas_de_la_veta(alfa)
    assert paneles == 0


# --- El sombreado -------------------------------------------------------------


def test_la_tela_no_se_sale_de_la_prenda() -> None:
    """Fuera de la máscara, la imagen sale idéntica al original.

    Es lo que garantiza el motor determinista por construcción, y lo que la
    edición generativa no puede garantizar.
    """
    rng = np.random.default_rng(3)
    foto = (rng.random((120, 120, 3)) * 40 + 180).astype(np.uint8)
    foto[30:90, 30:90] = 40  # una prenda oscura
    mascara = np.zeros((120, 120), dtype=np.uint8)
    mascara[30:90, 30:90] = 255

    salida = retexturizar(
        Image.fromarray(foto), Image.fromarray(mascara), _vichy(64, 8), repeticiones=4
    ).imagen
    fuera = mascara == 0
    assert np.array_equal(np.asarray(salida)[fuera], foto[fuera])


# --- El bloqueo estructural de la IA ------------------------------------------


def _prenda_de_prueba() -> tuple[Image.Image, Image.Image]:
    """Una camiseta sintética con pliegues y una costura, y su máscara."""
    alto, ancho = 240, 200
    yy, xx = np.mgrid[0:alto, 0:ancho].astype(np.float32)
    pliegues = 0.75 + 0.2 * np.sin(xx / 9.0) + 0.05 * np.sin(yy / 23.0)
    px = np.stack([0.8 * pliegues, 0.15 * pliegues, 0.2 * pliegues], axis=-1)
    px[:, 98:102] *= 0.5  # una costura
    mascara = np.zeros((alto, ancho), dtype=np.uint8)
    mascara[20:220, 30:170] = 255
    fondo = np.full((alto, ancho, 3), 0.9, dtype=np.float32)
    dentro = (mascara > 0)[..., None]
    img = np.where(dentro, px, fondo)
    return (
        Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), mode="RGB"),
        Image.fromarray(mascara, mode="L"),
    )


def test_si_la_ia_devuelve_otra_prenda_sale_la_prenda_exacta() -> None:
    """La garantía: una salida de IA que no es la prenda se descarta entera.

    Medido con salidas reales: la espalda de la camiseta, un vestido de punto
    sin abertura, un vestido de cuello cerrado. Aquí, una imagen sin nada que
    ver.
    """
    render, mascara = _prenda_de_prueba()
    otra = np.random.default_rng(7).random((240, 200, 3))
    bloqueado = bloquear_estructura(
        render, Image.fromarray((otra * 255).astype(np.uint8), mode="RGB"), mascara
    )
    assert bloqueado.aportado == 0.0
    assert np.array_equal(np.asarray(bloqueado.imagen), np.asarray(render))


def test_la_ia_no_puede_mover_una_costura_ni_un_pliegue() -> None:
    """Aunque la IA coincida y se acepte, la estructura sigue siendo la del render.

    La IA aquí es el render con textura fina encima y una costura INVENTADA.
    La textura puede entrar; la costura nueva no, porque es estructura.
    """
    render, mascara = _prenda_de_prueba()
    base = np.asarray(render, dtype=np.float32) / 255.0
    rng = np.random.default_rng(11)
    ia = base * (1.0 + 0.04 * rng.standard_normal(base.shape[:2]))[..., None]
    ia[:, 140:143] *= 0.4  # un corte que no existe en la prenda
    bloqueado = bloquear_estructura(
        render, Image.fromarray((np.clip(ia, 0, 1) * 255).astype(np.uint8), mode="RGB"), mascara
    )
    salida = np.asarray(bloqueado.imagen, dtype=np.float32) / 255.0

    # Se compara con el RENDER en las mismas columnas: la prenda tiene pliegues,
    # y comparar con columnas vecinas mediría el pliegue, no el corte.
    referencia = base[40:200, :]
    trozo = salida[40:200, :]
    en_el_corte = float((trozo[:, 140:143] / referencia[:, 140:143]).mean())
    assert en_el_corte > 0.93, f"el corte inventado no aparece ({en_el_corte:.2f})"
    en_la_costura = float((trozo[:, 98:102] / referencia[:, 98:102]).mean())
    assert 0.9 < en_la_costura < 1.1, "la costura de la prenda sigue como estaba"
