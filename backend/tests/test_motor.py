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


def test_el_canto_de_una_prenda_clara_no_se_agujerea() -> None:
    """Una prenda blanca sobre fondo casi igual: el borde no se llena de huecos.

    La camiseta blanca de ejemplo mide 217 en el canto de la manga, lo mismo
    que el fondo, y 205 en su interior sombreado. Votando por color, el canto
    se parecía más al fondo que a la prenda, y la máscara salía agujereada POR
    DENTRO; vestida de terracota, asomaba un ribete blanco deshilachado.
    """
    lado, alto = 800, 400
    borde_izq, borde_der = 200, 600
    # Como en la foto: el interior en sombra (205) y un filo claro de 4 px en
    # el canto (220), del color del fondo (217).
    fila = np.full(lado, 217.0, dtype=np.float32)
    fila[borde_izq:borde_der] = 205.0
    fila[borde_izq : borde_izq + 4] = 220.0
    fila[borde_der - 4 : borde_der] = 220.0
    foto = np.broadcast_to(fila[None, :], (alto, lado))
    guia = Image.fromarray(foto.astype(np.uint8)).convert("RGB")

    mascara = np.zeros((alto, lado), dtype=np.uint8)
    mascara[:, borde_izq:borde_der] = 255
    alfa = np.asarray(_pegar_al_borde(Image.fromarray(mascara), guia, (lado, alto)), dtype=np.float32)
    dentro = alfa[:, borde_izq + 3 : borde_der - 3] / 255.0
    assert dentro.min() > 0.97, f"hay huecos dentro de la prenda (mínimo {dentro.min():.2f})"


def test_el_canto_se_mezcla_con_el_fondo_y_no_con_la_prenda_vieja() -> None:
    """En el canto, la tela nueva se funde con el FONDO de al lado.

    Mezclarla con la foto tal cual volvía a meter la prenda vieja en el borde:
    una camiseta blanca vestida de oscuro salía con un ribete blanco.
    """
    lado = 120
    foto = np.full((lado, lado, 3), 128, dtype=np.uint8)  # fondo gris
    foto[20:100, 20:100] = 250  # prenda blanca
    mascara = np.zeros((lado, lado), dtype=np.uint8)
    mascara[24:96, 24:96] = 255
    # Un canto a medias sobre la propia prenda blanca, como el de una máscara
    # que no llega del todo al borde.
    mascara[20:100, 20:24] = 128
    oscura = Image.new("RGB", (32, 32), (40, 40, 40))

    salida = np.asarray(
        retexturizar(Image.fromarray(foto), Image.fromarray(mascara), oscura, repeticiones=3).imagen,
        dtype=np.float32,
    )
    canto = salida[40:80, 20:24].mean()
    assert canto < 128, f"el canto trae el blanco de la prenda vieja ({canto:.0f})"
    assert np.array_equal(salida[:, :18], foto[:, :18]), "el fondo sigue intacto"


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


def test_la_manga_llega_entera_hasta_su_borde() -> None:
    """A tamaño de foto, TODA la manga lleva su veta, también el filo.

    Los paneles se deciden a 320 px y se ampliaban por vecino más próximo. En la
    camiseta de rayas del usuario, a 1536 px, eso dejaba la costura en escalones
    de 5 px y una franja a lo largo del filo de la manga con la raya vertical del
    cuerpo: un serrucho azul y blanco por todo el hombro.
    """
    escala = 4
    pequena = _camiseta(inclinacion_grados=45)
    alfa = np.kron(pequena, np.ones((escala, escala), dtype=np.float32))
    x, _, paneles = coordenadas_de_la_veta(alfa)
    assert paneles == 2

    alto, ancho = alfa.shape
    yy, xx = np.mgrid[0:alto, 0:ancho].astype(np.float32) / escala
    angulo = np.radians(45)
    filo = np.zeros_like(alfa, dtype=bool)
    for lado in (-1, 1):
        hombro = np.array([200 + lado * 60, 140])
        direccion = np.array([lado * np.sin(angulo), np.cos(angulo)])
        rel = np.stack([xx - hombro[0], yy - hombro[1]], axis=-1)
        a_lo_largo = rel @ direccion
        de_lado = np.abs(rel @ np.array([direccion[1], -direccion[0]]))
        # El filo exterior de la manga, lejos del hombro y de la punta.
        filo |= (a_lo_largo > 40) & (a_lo_largo < 130) & (de_lado > 19) & (de_lado < 22)
    filo &= alfa > 0.5
    identidad = np.arange(ancho, dtype=np.float32)[None, :]
    girados = np.abs(x - identidad)[filo] > 0.5
    assert girados.mean() > 0.99, f"solo el {girados.mean():.1%} del filo lleva la veta de la manga"


def test_el_hueco_entre_brazo_y_cuerpo_sigue_siendo_fondo() -> None:
    """El cierre morfológico no puede rellenar el hueco entre la manga y el cuerpo.

    Pasaba en el vestido negro del usuario: el hueco de unos 5 px entre el brazo
    y el torso se sellaba entero, y la tela salía en dos bloques pegados al
    cuerpo. Aquí, una prenda oscura con dos mangas separadas del torso por un
    hueco más estrecho que el cierre.
    """
    from app.textil.segmentar import segmentar_prenda

    alto, ancho = 512, 400
    foto = np.full((alto, ancho, 3), 238, dtype=np.uint8)
    foto[60:480, 154:246] = 25  # torso
    foto[60:100, 110:290] = 25  # hombros
    foto[60:330, 110:146] = 25  # manga izquierda: hueco de 8 px hasta el torso
    foto[60:330, 254:290] = 25  # manga derecha
    recorte = segmentar_prenda(Image.fromarray(foto))
    alfa = np.asarray(recorte.mascara, dtype=np.float32) / 255.0
    hueco = np.concatenate([alfa[140:320, 148:152].ravel(), alfa[140:320, 248:252].ravel()])
    assert hueco.mean() < 0.1, f"el hueco sale como prenda ({hueco.mean():.2f})"
    assert alfa[200:300, 160:240].mean() > 0.99, "el torso sigue entero"
    assert alfa[150:300, 115:140].mean() > 0.99, "la manga sigue entera"


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
