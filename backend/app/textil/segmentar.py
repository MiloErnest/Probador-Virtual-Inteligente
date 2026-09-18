"""Recortar la prenda del fondo de la fotografía o del boceto.

QUÉ RESUELVE
------------
Antes de poder estampar una tela sobre una prenda hay que saber qué píxeles
son prenda. Esa máscara se calcula UNA vez al subir la imagen y se guarda: se
necesita idéntica para cada tela que se pruebe, y recalcularla convertiría
«probar diez telas» en diez recortes en lugar de diez multiplicaciones.

POR QUÉ RELLENO DESDE LOS BORDES Y NO UN FILTRO POR COLOR
---------------------------------------------------------
Lo fácil sería «borra todo lo que sea casi blanco». Con una prenda BLANCA
sobre fondo claro, eso borra la prenda.

Aquí se parte de los bordes de la imagen —donde con certeza hay fondo— y se
extiende hacia dentro mientras el color siga pareciéndose. Al llegar a la
prenda, el color cambia y la expansión se detiene. Una camisa blanca rodeada
de prenda sigue intacta porque el relleno nunca llega a ella: no hay camino
desde el borde que no cruce el contorno.

Es la misma idea que la varita mágica de un editor de imagen, y es la técnica
que ya se probó contra las fotografías reales de este proyecto.

POR QUÉ FUNCIONA IGUAL CON UN BOCETO
------------------------------------
Un boceto es papel blanco con líneas oscuras. El relleno entra desde el borde,
avanza por el papel y se para al chocar con el trazo del contorno. Lo que queda
dentro —el papel encerrado por el dibujo— es exactamente la prenda. Sale gratis
por la misma razón que funciona en una foto.

Su punto débil es distinto: si el contorno tiene un hueco, el relleno se cuela
dentro y se come el dibujo. Por eso se mide la cobertura y se avisa.

LÍMITE CONOCIDO Y MEDIDO
------------------------
Una prenda casi del mismo color que el fondo no se puede recortar así, y no es
cuestión de ajustar el umbral. En la camiseta blanca del catálogo de este
proyecto el fondo vale (217,218,212) y hay tela en sombra que vale
(217,217,217): distancia 6, cuando el propio fondo varía 7 a lo largo del
borde. No hay información que separar. Se detecta y se avisa (`dudoso`).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter

from app.textil.filtros import desenfocar

# --- Parámetros, todos medidos contra fotografías reales --------------------

#: Resolución a la que se calcula la máscara.
#:
#: El recorte NO necesita la resolución completa: sus bordes se suavizan
#: después, y el relleno en Python sobre dos millones de píxeles tarda
#: segundos. A 512 px el resultado es indistinguible y cuesta una fracción.
LADO_DE_TRABAJO = 512

#: Margen sobre la variación medida del propio fondo.
FACTOR_MARGEN = 2.0

#: Suelo y techo del umbral. El techo es lo que impide comerse una prenda
#: clara: por debajo de los 26 medidos en la camiseta blanca.
UMBRAL_MINIMO = 10.0
UMBRAL_MAXIMO = 18.0

#: Suavizado del mapa de distancias ANTES de decidir qué es fondo.
#:
#: POR QUÉ AQUÍ Y NO DESPUÉS
#: -------------------------
#: Una prenda oscura sobre fondo claro deja un halo de sombra alrededor, y el
#: umbral lo corta de forma irregular: la chaqueta de cuero salía con el
#: contorno dentado, con picos de varios píxeles por toda la manga.
#:
#: El primer intento fue limpiarlo DESPUÉS, con una apertura morfológica sobre
#: la máscara ya hecha. Funcionó en la chaqueta y estropeó la camiseta blanca:
#: erosionar borra lo fino, y lo fino que borró fue prenda de verdad — un 7%
#: de la camiseta desapareció, y volvió a salir el agujero que acabábamos de
#: tapar.
#:
#: La lección: el ruido estaba en la DECISIÓN, no en el resultado. Suavizando
#: el mapa de distancias antes de umbralizarlo, los picos desaparecen y la
#: cobertura de la camiseta no se mueve ni una milésima (0,1546 con y sin).
#:
#: Medido: 1,0 limpia la chaqueta; 3,5 empieza a engordar la silueta y a juntar
#: las perneras del vaquero por arriba.
SUAVIZADO_DE_DECISION = 1.0

#: Radio del cierre morfológico, en píxeles de la imagen de trabajo.
#:
#: Una prenda clara tiene pliegues en sombra casi del color del fondo. El
#: relleno entra por ahí y TUNELA hacia dentro, dejando la prenda rayada. Un
#: cierre —dilatar y luego erosionar— sella túneles más finos que el radio y
#: deja la silueta prácticamente igual.
#:
#: Medido: con 3 quedaba una ranura abierta desde el bajo de la camiseta
#: blanca. Con 5 se cierra. Y se comprobó que NO fusiona las dos perneras del
#: vaquero, que es el riesgo de agrandar el núcleo: siguen separadas por 15
#: columnas incluso con radio 7.
RADIO_CIERRE = 5

#: Si el fondo se come más que esto, el recorte no vale.
MAXIMO_BORRADO = 0.92

#: Por debajo de esta cobertura la prenda ha quedado a tiras.
COBERTURA_MINIMA = 0.04


@dataclass(frozen=True)
class Recorte:
    """Resultado del recorte."""

    #: Máscara en escala de grises, del tamaño de la imagen original.
    #: 255 = prenda, 0 = fondo, valores intermedios en el borde suavizado.
    mascara: Image.Image
    #: Fracción de la imagen que ocupa la prenda, de 0 a 1.
    cobertura: float
    #: El recorte no es de fiar y conviene avisar antes de gastar en pruebas.
    dudoso: bool
    #: Caja que ocupa la prenda, en píxeles de la imagen original.
    caja: tuple[int, int, int, int]


def segmentar_prenda(imagen: Image.Image) -> Recorte:
    """Devuelve la máscara de la prenda dentro de la imagen."""
    original = imagen.size

    # CAMINO RÁPIDO: la imagen ya trae transparencia.
    #
    # Un boceto exportado en PNG con fondo transparente ya lleva la respuesta
    # dentro. Adivinarla otra vez sería peor: el canal alfa es exacto y el
    # relleno es una aproximación.
    if imagen.mode in ("RGBA", "LA") and _tiene_transparencia(imagen):
        alfa = imagen.getchannel("A")
        return _empaquetar(alfa, original)

    trabajo = _reducir(imagen.convert("RGB"), LADO_DE_TRABAJO)
    px = np.asarray(trabajo, dtype=np.float32)
    alto, ancho = px.shape[:2]

    # Color de referencia del fondo: la mediana de las cuatro esquinas. Con la
    # mediana, una esquina rara —una sombra, una marca de agua— no arrastra el
    # resultado.
    esquinas = np.stack(
        [px[0, 0], px[0, ancho - 1], px[alto - 1, 0], px[alto - 1, ancho - 1]]
    )
    fondo = np.median(esquinas, axis=0)

    # UMBRAL ADAPTATIVO, NO FIJO.
    #
    # Un solo número no vale para todas las fotos: en una camiseta blanca la
    # separación entre prenda y fondo es de 26, y en una chaqueta negra es
    # enorme. Se mide cuánto varía el fondo a lo largo del borde —donde con
    # certeza no hay prenda— y se deja margen sobre esa variación.
    distancia = desenfocar(np.linalg.norm(px - fondo, axis=2), SUAVIZADO_DE_DECISION)
    borde = np.concatenate(
        [distancia[0, :], distancia[-1, :], distancia[:, 0], distancia[:, -1]]
    )
    umbral = float(np.clip(np.percentile(borde, 95) * FACTOR_MARGEN, UMBRAL_MINIMO, UMBRAL_MAXIMO))

    similar = distancia <= umbral
    alcanzado = _rellenar_desde_el_borde(similar)

    borrado = float(alcanzado.mean())
    if borrado > MAXIMO_BORRADO:
        # El relleno se ha llevado casi todo: la prenda era del color del fondo
        # o la foto no tiene fondo liso. Mejor devolver la imagen entera que
        # una máscara vacía, y marcarla como dudosa.
        entera = Image.new("L", trabajo.size, 255)
        return _empaquetar(entera, original, forzar_dudoso=True)

    prenda = (~alcanzado).astype(np.uint8) * 255
    mascara = Image.fromarray(prenda, mode="L")

    # PASO 1. Cierre morfológico: dilatar y después erosionar. Sella los
    # túneles por los que el relleno se coló entre los pliegues.
    lado = RADIO_CIERRE * 2 + 1
    mascara = mascara.filter(ImageFilter.MaxFilter(lado)).filter(ImageFilter.MinFilter(lado))

    # PASO 2. Tapar las cavidades que quedan dentro.
    #
    # El cierre por sí solo NO basta, y se vio en la camiseta blanca: sella la
    # BOCA del túnel, pero la cavidad que hay detrás sigue ahí, y sale como un
    # agujero blanco en mitad de la prenda.
    #
    # Ahora que la boca está sellada, esa cavidad ya no se alcanza desde el
    # borde de la imagen. Así que basta con volver a rellenar desde el borde y
    # quedarse con lo que NO se alcanza: es fondo encerrado, o sea, prenda.
    solida = np.asarray(mascara, dtype=np.uint8) > 127
    fuera = _rellenar_desde_el_borde(~solida)
    mascara = Image.fromarray((~fuera).astype(np.uint8) * 255, mode="L")

    return _empaquetar(mascara, original)


def _tiene_transparencia(imagen: Image.Image) -> bool:
    extremos = imagen.getchannel("A").getextrema()
    return extremos is not None and extremos[0] < 250


def _reducir(imagen: Image.Image, lado: int) -> Image.Image:
    if max(imagen.size) <= lado:
        return imagen
    escala = lado / max(imagen.size)
    nuevo = (max(1, round(imagen.width * escala)), max(1, round(imagen.height * escala)))
    return imagen.resize(nuevo, Image.Resampling.BILINEAR)


def _rellenar_desde_el_borde(similar: np.ndarray) -> np.ndarray:
    """Marca todo lo que se alcanza desde el borde sin salir de `similar`.

    Recorrido en anchura sobre índices planos. Se eligió esto y no una
    propagación vectorizada porque es evidentemente correcto de leer, y a la
    resolución de trabajo tarda una fracción de segundo. Optimizarlo sería
    cambiar claridad por un tiempo que nadie va a notar: esto corre una vez por
    imagen subida, en segundo plano.
    """
    alto, ancho = similar.shape
    alcanzado = np.zeros_like(similar, dtype=bool)
    plano = similar.reshape(-1)
    visto = alcanzado.reshape(-1)

    cola: deque[int] = deque()

    def sembrar(indice: int) -> None:
        if plano[indice] and not visto[indice]:
            visto[indice] = True
            cola.append(indice)

    for x in range(ancho):
        sembrar(x)
        sembrar((alto - 1) * ancho + x)
    for y in range(alto):
        sembrar(y * ancho)
        sembrar(y * ancho + ancho - 1)

    while cola:
        i = cola.popleft()
        y, x = divmod(i, ancho)
        if x > 0:
            sembrar(i - 1)
        if x < ancho - 1:
            sembrar(i + 1)
        if y > 0:
            sembrar(i - ancho)
        if y < alto - 1:
            sembrar(i + ancho)

    return alcanzado


def _empaquetar(
    mascara: Image.Image, tamano_original: tuple[int, int], *, forzar_dudoso: bool = False
) -> Recorte:
    """Devuelve la máscara al tamaño original, suavizada y medida."""
    if mascara.size != tamano_original:
        mascara = mascara.resize(tamano_original, Image.Resampling.BILINEAR)

    # Suavizado del borde. Sin él, la tela termina en un escalón dentado que
    # delata el montaje; con un desenfoque de un píxel por cada 400 de ancho,
    # el canto se funde y no se nota.
    radio = max(1.0, tamano_original[0] / 400)
    mascara = mascara.filter(ImageFilter.GaussianBlur(radio))

    datos = np.asarray(mascara, dtype=np.float32) / 255.0
    cobertura = float(datos.mean())

    solida = datos > 0.5
    if solida.any():
        filas = np.where(solida.any(axis=1))[0]
        columnas = np.where(solida.any(axis=0))[0]
        caja = (int(columnas[0]), int(filas[0]), int(columnas[-1]) + 1, int(filas[-1]) + 1)
    else:
        caja = (0, 0, tamano_original[0], tamano_original[1])

    return Recorte(
        mascara=mascara,
        cobertura=cobertura,
        dudoso=forzar_dudoso or cobertura < COBERTURA_MINIMA or cobertura > MAXIMO_BORRADO,
        caja=caja,
    )
