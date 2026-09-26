"""Convertir la FOTO de un rollo de tela en un mosaico que se pueda estampar.

ES EL PASO QUE HACEN LOS DIGITALIZADORES DE TELA
------------------------------------------------
Los sistemas de visualización textil que funcionan (Vizoo, Swatchbook, los
configuradores de tienda) no estampan la foto del rollo tal cual: la escanean o
la fotografían en condiciones controladas y sacan de ella un mosaico LIMPIO —sin
la luz del almacén, sin los dobleces, repetible—. Aquí se hace lo mismo con una
foto de móvil, que es lo que tiene una tienda de barrio.

MEDIR Y SINTETIZAR, SEPARADOS
-----------------------------
Cada clase de tela tiene una función que MIDE (`color_propio`, `medir_rayas`) y
otra que SINTETIZA el mosaico a partir de las medidas (`muestra_lisa`,
`muestra_rayas`). Entre las dos se corrige el balance de blancos, que es de la
FOTO y no de cada tela: todas las telas de una misma estantería salieron con la
misma luz.

- **Lisa**: color medido, con una trama de tafetán limpia encima. NO el grano
  de la foto: en un recorte de 80 px de una foto de móvil, lo que parece grano
  es ruido del sensor y bloques JPEG, y estamparlo repetiría ese ruido por toda
  la prenda.
- **Rayas**: se miden los dos colores, el período y la proporción de cada
  franja, y se reconstruye la raya limpia. Una raya fotografiada en un rollo sale
  estrechándose por la perspectiva y curvada por el rollo; estamparla así
  metería la perspectiva del almacén en la camisa.
- **Estampado de zona amplia**: se le quita la luz y se cierra la junta. El
  dibujo es el de la foto, sin reinterpretar.

LO QUE NO SE PUEDE HACER Y NO SE FINGE
--------------------------------------
Sacar de una foto la composición o el gramaje: eso lo sabe la tienda y va a la
ficha a mano. Ni el color real de una tela fotografiada en sombra total: lo que
no llegó al sensor no se recupera dividiendo.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from app.textil.filtros import desenfocar, media_en_ventana
from app.textil.tejido_ia import LADO, hacer_repetible

LUMINANCIA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)

#: Relieve de la trama, en fracción del brillo. Con 0 la tela sale plana como un
#: color de pintura; por encima de ~0,1 parece arpillera.
RELIEVE = 0.06

#: Hilos que cruzan el mosaico. A 1024 px son 8 px por hilo, que se ve en la
#: ficha y se funde en la prenda, donde el mosaico se reduce varias veces.
HILOS = 128

#: A qué color se lleva un tejido blanco medido: el de un blanco de tela real
#: iluminado de frente, ligeramente cálido. Es el mismo del «Blanco óptico» del
#: catálogo, para que un blanco nuevo y uno viejo se vean igual.
BLANCO_OBJETIVO = np.array([238, 238, 235], dtype=np.float32) / 255.0

#: Cuánto puede llegar a corregirse un canal. Más allá, la foto no tenía blanco
#: de verdad o estaba demasiado oscura, y corregir inventaría el color.
GANANCIA_MAXIMA = 2.2

#: El canal más alto de un color corregido no pasa de aquí. Un tejido blanco
#: real no llega al blanco puro de la pantalla, y reservar este margen es lo
#: que permite que un marfil siga siendo marfil al lado de un blanco.
TECHO_DE_COLOR = 0.97

#: Cuánto pesa el brillo frente a la cromaticidad al separar los dos colores
#: de una raya. Poco: lo justo para que blanco y rosa palo no se confundan.
PESO_DEL_BRILLO = 0.5

#: Por debajo de esta saturación, la franja clara de una raya es BLANCA y sirve
#: para medir la exposición del rollo.
SATURACION_DEL_BLANCO = 0.18

#: Cuánto se puede subir la exposición de un rollo. Medido: el de más sombra del
#: estante de rayas —el azul rey, arriba del todo— necesitó 1,16. El techo deja
#: margen para una foto peor iluminada; más allá se estaría adivinando.
EXPOSICION_MAXIMA = 1.6


# --- Luz --------------------------------------------------------------------


def quitar_luz(px: np.ndarray, radio: float) -> np.ndarray:
    """Divide la iluminación y deja el color propio de la tela.

    `radio` tiene que ser MUCHO mayor que cualquier dibujo de la tela: si no, el
    cálculo de la luz sigue al dibujo y dividir lo aplana. Pasó con las rayas:
    con un radio de 4 px en un recorte de 28, el blanco de la raya salía gris.
    """
    brillo = px @ LUMINANCIA
    luz = np.maximum(desenfocar(brillo, radio), 1e-3)
    # Se devuelve la MEDIA DE LA LUZ, no la mediana del brillo. En una tela lisa
    # dan lo mismo; en un estampado, la mediana cae entre el fondo y el dibujo, y
    # reescalar a ella oscurecía el fondo: el floral de acuarela, crudo claro en
    # la foto, salía gris.
    medio = float(luz.mean())
    return np.clip(px * (medio / luz)[..., None], 0.0, 1.0)


def quitar_luz_de_rayas(px: np.ndarray, periodo: float | None) -> np.ndarray:
    """La luz de una raya se quita por filas y por columnas, por separado.

    Cada fila contiene los dos colores en la misma proporción, así que la media
    de la fila es luz pura: es la curvatura del rollo. A lo largo del rollo, la
    luz cambia despacio y se estima suavizando la media de las columnas sobre
    varias rayas, para que la raya en sí no cuente como luz.
    """
    brillo = px @ LUMINANCIA
    fila = np.maximum(brillo.mean(axis=1, keepdims=True), 1e-3)
    px = px * (float(fila.mean()) / fila)[..., None]

    columnas = (px @ LUMINANCIA).mean(axis=0)
    ventana = max(3, round(3 * periodo)) if periodo else max(3, columnas.size // 4)
    tendencia = media_en_ventana(columnas[None, :], ventana // 2, 1)[0]
    tendencia = np.maximum(tendencia, 1e-3)
    return np.clip(px * (float(tendencia.mean()) / tendencia)[None, :, None], 0.0, 1.0)


def ganancias_de_blanco(blanco_medido: np.ndarray) -> np.ndarray:
    """Ganancia por canal que lleva un blanco medido al blanco de referencia.

    Es el «parche blanco» de toda la vida: si algo en la foto es blanco, lo que
    le haga falta para verse blanco es lo que le hace falta a toda la foto. Las
    tiendas iluminan con luz fría o cálida y fotografían con el móvil; sin esto,
    un blanco sale azulado y un marfil, verde.
    """
    ganancia = BLANCO_OBJETIVO / np.maximum(blanco_medido, 1e-3)
    return np.clip(ganancia, 1.0 / GANANCIA_MAXIMA, GANANCIA_MAXIMA).astype(np.float32)


def aplicar_ganancias(color: np.ndarray, ganancia: np.ndarray) -> np.ndarray:
    """Aplica la corrección SIN perder el tinte si algún canal se satura.

    Recortar cada canal a 1 por separado convierte un marfil en blanco puro: el
    canal que más sube se topa con el techo y los otros lo alcanzan. Se escala
    el color entero hasta que su canal más alto quepa, que conserva la
    proporción entre canales — y la proporción es el tinte.
    """
    corregido = np.asarray(color, dtype=np.float32) * ganancia
    techo = float(corregido.max())
    if techo > TECHO_DE_COLOR:
        corregido = corregido * (TECHO_DE_COLOR / techo)
    return np.clip(corregido, 0.0, 1.0)


def exponer_con_su_blanco(medida: dict) -> dict:
    """Corrige la exposición de un rollo a rayas usando su propia franja blanca.

    El balance de blancos es de la FOTO, pero la exposición no: el rollo de
    arriba del estante está en sombra y el de abajo al sol de la ventana. Si la
    franja clara es blanca de verdad (casi sin color), lo que le falte de brillo
    le falta a todo el rollo, y se sube a los dos colores por igual. Con una
    raya de dos colores —fucsia y naranja— no hay blanco con que medir y no se
    toca.
    """
    claro = np.asarray(medida["claro"], dtype=np.float32)
    saturacion = (claro.max() - claro.min()) / max(float(claro.max()), 1e-3)
    if saturacion > SATURACION_DEL_BLANCO:
        return medida

    factor = float(BLANCO_OBJETIVO @ LUMINANCIA) / max(float(claro @ LUMINANCIA), 1e-3)
    factor = float(np.clip(factor, 1.0, EXPOSICION_MAXIMA))
    return {
        **medida,
        "oscuro": aplicar_ganancias(medida["oscuro"], np.float32(factor)),
        "claro": aplicar_ganancias(claro, np.float32(factor)),
    }


# --- Lisas ------------------------------------------------------------------


def color_propio(recorte: Image.Image) -> np.ndarray:
    """El color de una tela lisa, sin la luz del almacén ni los brillos del doblez.

    Mediana de la tela ya sin luz, descartando el 10% más claro y el 10% más
    oscuro: el brillo del lomo del rollo y la sombra del pliegue no son el color
    de la tela, son luz.
    """
    px = _a_flotante(recorte)
    limpio = quitar_luz(px, max(px.shape[:2]) * 0.25).reshape(-1, 3)
    brillo = limpio @ LUMINANCIA
    bajo, alto = np.percentile(brillo, [10, 90])
    centro = limpio[(brillo >= bajo) & (brillo <= alto)]
    return np.median(centro if len(centro) else limpio, axis=0)


def muestra_lisa(color: np.ndarray) -> Image.Image:
    """Mosaico de una tela lisa: su color sobre una trama de tafetán limpia."""
    tela = np.broadcast_to(np.asarray(color, dtype=np.float32)[None, None, :], (LADO, LADO, 3))
    return _a_imagen(tela * (1.0 + RELIEVE * _trama()[..., None]))


# --- Rayas ------------------------------------------------------------------


def medir_rayas(recorte: Image.Image) -> dict:
    """Mide una tela a rayas: los dos colores, el período y la proporción.

    Los colores se separan con k-medias de dos grupos: en una raya bicolor hay
    exactamente dos colores. El período sale de la autocorrelación del perfil,
    y la proporción de cuánto ocupa cada color.
    """
    px = _a_flotante(recorte)
    periodo = _periodo_1d((px @ LUMINANCIA).mean(axis=0))
    limpio = quitar_luz_de_rayas(px, periodo)

    # SE AGRUPAN COLUMNAS, NO PÍXELES.
    #
    # Agrupando píxeles sueltos, la raya fucsia y naranja salía con el fucsia
    # ocupando el 66%, cuando por tono son 49% y 45%: el naranja en la sombra
    # del rollo se parecía más al fucsia que a sí mismo. En una raya vertical
    # cada columna es UN color de raya, y su media ya no tiene ni ruido ni
    # sombra.
    columnas = limpio.mean(axis=0)
    # Se agrupa por CROMATICIDAD (el color dividido por su brillo), que no
    # cambia con la luz, más un poco de brillo para que un blanco y un color
    # pálido sigan separándose. En RGB, el naranja en sombra del rollo se
    # parecía más al fucsia que a sí mismo.
    brillo = np.maximum(columnas @ LUMINANCIA, 1e-3)
    rasgos = np.concatenate(
        [columnas / brillo[:, None], PESO_DEL_BRILLO * brillo[:, None]], axis=1
    )
    _, etiquetas = _dos_colores(rasgos, orden=brillo)
    centros = np.stack([columnas[etiquetas == k].mean(axis=0) for k in range(2)])

    # El color se toma de las columnas del centro de cada raya: las del borde
    # son mezcla de los dos y lo ensuciarían.
    cambio = np.zeros(etiquetas.size, dtype=bool)
    cambio[1:] |= etiquetas[1:] != etiquetas[:-1]
    cambio[:-1] |= etiquetas[1:] != etiquetas[:-1]
    for k in range(2):
        interiores = (etiquetas == k) & ~cambio
        if interiores.any():
            centros[k] = np.median(limpio[:, interiores, :].reshape(-1, 3), axis=0)

    return {
        "oscuro": centros[0],
        "claro": centros[1],
        "periodo_px": periodo,
            "proporcion_oscuro": _proporcion_por_periodo(px, periodo),
    }


def muestra_rayas(medida: dict, *, periodos: int = 4) -> Image.Image:
    """Reconstruye la raya limpia con las medidas.

    `periodos` es cuántas rayas completas caben en el mosaico. Encima, la misma
    trama limpia que en las lisas, para que no parezca una raya de vector.
    """
    oscuro = np.asarray(medida["oscuro"], dtype=np.float32)
    claro = np.asarray(medida["claro"], dtype=np.float32)
    proporcion = float(medida["proporcion_oscuro"])

    x = (np.arange(LADO, dtype=np.float32) + 0.5) / LADO * periodos
    fase = x - np.floor(x)
    # Borde de medio píxel: una raya tejida no tiene corte de vector, pero
    # tampoco un degradado.
    borde = periodos / LADO
    peso = np.clip((proporcion - fase) / borde + 0.5, 0.0, 1.0)
    peso = np.minimum(peso, np.clip(fase / borde + 0.5, 0.0, 1.0))

    fila = oscuro[None, :] * peso[:, None] + claro[None, :] * (1.0 - peso[:, None])
    tela = np.broadcast_to(fila[None, :, :], (LADO, LADO, 3))
    return _a_imagen(tela * (1.0 + RELIEVE * _trama()[..., None]))


# --- Estampados -------------------------------------------------------------


def muestra_estampada(recorte: Image.Image, *, fondo_blanco: bool = False) -> Image.Image:
    """Mosaico de un estampado fotografiado en una zona amplia.

    El radio de la luz es un cuarto del lado: bastante mayor que cualquier motivo
    de un estampado, para que la flor no cuente como sombra.

    `fondo_blanco` usa el fondo del estampado como referencia de blanco. Solo
    cuando el fondo lo es de verdad —un algodón claro—: el floral de acuarela
    salió de la foto con mediana 147 de 255, gris, porque el móvil lo
    subexpuso. Sin esto, el catálogo lo enseñaba gris.
    """
    px = _a_flotante(recorte)
    limpio = quitar_luz(px, min(px.shape[:2]) * 0.25)
    if fondo_blanco:
        ganancia = ganancias_de_blanco(color_de_fondo(limpio))
        limpio = np.clip(limpio * ganancia[None, None, :], 0.0, 1.0)
    return hacer_repetible(_a_imagen(limpio))


def color_de_fondo(px: np.ndarray) -> np.ndarray:
    """El color del fondo de un estampado: el de sus píxeles más claros.

    Percentil 85 y no el máximo: el máximo es un brillo suelto o un píxel
    quemado; el 85 cae en el fondo, que en un estampado sobre blanco es la
    mayor parte de la tela.
    """
    return np.percentile(px.reshape(-1, 3), 85, axis=0).astype(np.float32)


# --- Auxiliares -------------------------------------------------------------


def _proporcion_por_periodo(px: np.ndarray, periodo: float | None) -> float:
    """Qué fracción de la raya ocupa el color oscuro, medida período a período.

    CÓMO SE LLEGÓ AQUÍ, PORQUE COSTÓ
    --------------------------------
    Medido a mano sobre las cinco rayas del estante, ampliadas: las cinco son de
    franjas iguales. Tres estimadores fallaron antes que éste:

    - k-medias sobre píxeles: el naranja en sombra se iba con el fucsia (0,66).
    - Proyección continua sobre el segmento entre los dos colores: 0,39–0,48.
    - Y el peor síntoma: en la raya azul rey, mover el recorte 4 píxeles hacía
      saltar la estimación de 0,40 a 0,25. Una medida así no mide nada.

    El que funciona es el umbral adaptativo clásico: en CADA período se pone el
    umbral a mitad entre el máximo y el mínimo de ese tramo, y se cuenta lo que
    queda por debajo. Cada tramo se compara con su propia luz, así que la sombra
    del estante no lo engaña. Resultado: 0,50–0,52 en las cinco, estable al
    mover el recorte, con ±0,03 de dispersión entre períodos.
    """
    brillo = px @ LUMINANCIA
    fila = np.maximum(brillo.mean(axis=1, keepdims=True), 1e-3)
    perfil = (brillo / fila * float(fila.mean())).mean(axis=0)
    paso = int(round(periodo)) if periodo else 0
    if paso < 2 or paso > perfil.size:
        return 0.5

    fracciones = []
    for inicio in range(0, perfil.size - paso + 1, paso):
        tramo = perfil[inicio : inicio + paso]
        umbral = (float(tramo.max()) + float(tramo.min())) / 2.0
        fracciones.append(float((tramo < umbral).mean()))
    return float(np.mean(fracciones))


def _trama() -> np.ndarray:
    """Relieve de un tafetán: un hilo por encima, uno por debajo.

    Trama y urdimbre se alternan como un tablero; cada hilo es un abombamiento
    coseno. Repetible por construcción, porque HILOS divide a LADO.
    """
    paso = LADO / HILOS
    eje = np.arange(LADO, dtype=np.float32)
    x, y = np.meshgrid(eje, eje)
    celda = (np.floor(x / paso) + np.floor(y / paso)) % 2 == 0
    abombado_x = np.cos(np.pi * ((x % paso) / paso - 0.5))
    abombado_y = np.cos(np.pi * ((y % paso) / paso - 0.5))
    relieve = np.where(celda, abombado_y, abombado_x)
    return (relieve - relieve.mean()).astype(np.float32)


def _dos_colores(
    muestras: np.ndarray, vueltas: int = 12, orden: np.ndarray | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """k-medias con dos grupos. El primero es siempre el más oscuro.

    `orden` es el brillo de cada muestra, para cuando los rasgos con que se
    agrupa no son colores y no se puede calcular de ellos.
    """
    brillo = orden if orden is not None else muestras[:, :3] @ LUMINANCIA
    centros = np.stack(
        [muestras[brillo <= np.percentile(brillo, 25)].mean(axis=0),
         muestras[brillo >= np.percentile(brillo, 75)].mean(axis=0)]
    )
    etiquetas = np.zeros(len(muestras), dtype=np.int64)
    for _ in range(vueltas):
        distancias = np.linalg.norm(muestras[:, None, :] - centros[None, :, :], axis=2)
        etiquetas = distancias.argmin(axis=1)
        for k in range(2):
            if (etiquetas == k).any():
                # Mediana y no media: los píxeles del borde entre rayas son
                # mezcla de los dos colores y no deben arrastrar ninguno.
                centros[k] = np.median(muestras[etiquetas == k], axis=0)
    if brillo[etiquetas == 0].mean() > brillo[etiquetas == 1].mean():
        centros = centros[::-1].copy()
        etiquetas = 1 - etiquetas
    return centros, etiquetas


def _periodo_1d(perfil: np.ndarray) -> float | None:
    perfil = perfil - perfil.mean()
    n = perfil.size
    espectro = np.fft.rfft(perfil, n=2 * n)
    auto = np.fft.irfft(espectro * np.conj(espectro))[:n]
    auto = auto / (auto[0] or 1.0)
    bajado = False
    for k in range(2, n // 2):
        if auto[k] < 0:
            bajado = True
        if bajado and auto[k] > 0.3 and auto[k] >= auto[k - 1] and auto[k] >= auto[k + 1]:
            return float(k)
    return None


def _a_flotante(imagen: Image.Image) -> np.ndarray:
    return np.asarray(imagen.convert("RGB"), dtype=np.float32) / 255.0


def _a_imagen(px: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(px * 255.0, 0, 255).astype(np.uint8), mode="RGB")
