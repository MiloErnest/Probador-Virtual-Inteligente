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

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter

from app.textil.filtros import desenfocar, filtro_guiado

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

#: Anchura del marco del que se aprende el fondo, en fracción del lado corto.
FRANJA_DEL_MARCO = 0.06

#: Cuántas veces se reajusta el fondo descartando lo que no encaja. Dos bastan:
#: la primera quita la prenda que toque el marco, la segunda afina.
VUELTAS_DEL_AJUSTE = 2

#: En un boceto, cuánto tiene que hundirse un píxel respecto a su entorno para
#: ser TRAZO y frenar el relleno. Mismo criterio que el retexturizado: el
#: contorno a lápiz hunde un 73%, el rayado de sombra un 11%.
TRAZO_DE_BARRERA = 0.30

#: Cuántas veces se engrosa el trazo para sellar los cortes del contorno.
SELLADO_DEL_TRAZO = 1

#: Hasta dónde puede entrar el relleno en la máscara de un boceto para comerse
#: la sombra que rodea la figura, en píxeles de la imagen de trabajo. Medido: la
#: sombra del croquis de referencia ocupa 10–15 px.
ANCHO_DE_SOMBRA = 14

#: GrabCut: qué parte de la máscara es prenda SEGURA (núcleo tras erosionar) y
#: hasta dónde puede crecer (banda tras dilatar), en fracción del lado corto.
NUCLEO_SEGURO = 0.02
BANDA_DUDOSA = 0.06
VUELTAS_DE_GRABCUT = 4

#: Cuántas veces el umbral tiene que alejarse un píxel del fondo para contar
#: como color CLARAMENTE distinto, y qué parte de la prenda tiene que serlo
#: para fiarse del color al inicializar GrabCut.
FACTOR_DE_COLOR_SEGURO = 2.5
PRENDA_DISTINTA_MINIMA = 0.5

#: Si GrabCut cambia la cobertura más que esto, se descarta su resultado.
CAMBIO_MAXIMO = 0.40

#: Anchura de la franja dudosa alrededor del borde ampliado, en píxeles de la
#: imagen de trabajo: lo que se reclasifica con el color local. Cubre el error
#: de ampliar la máscara y el de GrabCut, que trabaja a esa resolución.
FRANJA_DEL_BORDE = 2.0

#: Cuánto borde hace falta en la foto para que el filtro guiado lo respete. Bajo,
#: para pegarse a bordes débiles como blanco sobre gris claro.
EPS_DEL_BORDE = 1e-4

#: Saturación a partir de la cual un píxel es FIGURA y no prenda.
#:
#: En un figurín hay una persona dibujada, y la persona no es la prenda. Si se
#: deja dentro del recorte, la tela le pinta la cara, el pelo y los brazos —que
#: es exactamente lo que pasaba, y lo que hacía que el resultado no fuera «tu
#: dibujo con otra tela» sino otra cosa.
#:
#: Se separan por saturación porque es lo que de verdad los distingue: el lápiz
#: es gris —acromático— y la piel y el pelo se colorean. Medido en el croquis
#: de referencia: el vestido tiene saturación 0,020 de mediana y 0,057 en el
#: percentil 90; la figura está por encima de 0,10. Hay un orden de magnitud
#: entre las dos cosas, así que el umbral no es delicado.
#:
#: La regla clásica de tono de piel en RGB (Kovac) NO sirve aquí: está ajustada
#: a fotografías y pide |R−G| > 15, que una piel dibujada en beige pálido no
#: cumple. Detectaba el 0,2% de lo que hay que detectar.
SATURACION_DE_LA_FIGURA = 0.10

#: Croma mínimo (máximo menos mínimo de los canales, sobre 255) de la figura.
#: Ver `_quitar_la_figura`.
CROMA_DE_LA_FIGURA = 18.0

#: Si la «figura» ocupa más que esto del recorte, NO es una figura.
#:
#: Es la salvaguarda que hace segura la regla anterior. Una prenda de color
#: cálido —un lino terracota, una seda burdeos— también es saturada, y sin este
#: tope el recorte se comería la prenda entera. Si lo detectado es casi todo,
#: lo que hay es una prenda de color, no una persona, y no se quita nada.
#:
#: Medido: el croquis del vestido da 0,05 después de cerrar y rellenar. Una
#: fotografía de prenda lisa cálida daría cerca de 1.
MAXIMO_DE_FIGURA = 0.30

#: Radios de la limpieza de la figura, en píxeles de la imagen de trabajo.
#:
#: El primero quita el fleco de color que deja el escaneo a lo largo de cada
#: línea de lápiz —cromatismo del sensor, no dibujo—. El segundo une el pelo
#: alrededor de la cara para que la cara quede encerrada y el relleno la tape:
#: la cara es papel en blanco y por sí sola no tiene color que detectar.
RADIO_LIMPIEZA_DE_FIGURA = 2
RADIO_UNION_DE_FIGURA = 6

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


def segmentar_prenda(imagen: Image.Image, *, boceto: bool = False) -> Recorte:
    """Devuelve la máscara de la prenda dentro de la imagen.

    `boceto` cambia el último paso. En una fotografía, GrabCut aprende los
    colores de prenda y fondo y corta por el borde real; en un dibujo, el
    contorno a lápiz ya es la mejor barrera que hay, y un modelo de color
    confundiría el papel blanco con un vestido blanco.
    """
    original = imagen.size

    # CAMINO RÁPIDO: la imagen ya trae transparencia.
    #
    # Un boceto exportado en PNG con fondo transparente ya lleva la respuesta
    # dentro. Adivinarla otra vez sería peor: el canal alfa es exacto y el
    # relleno es una aproximación.
    if imagen.mode in ("RGBA", "LA") and _tiene_transparencia(imagen):
        alfa = imagen.getchannel("A")
        trabajo = _reducir(imagen.convert("RGB"), LADO_DE_TRABAJO)
        alfa = alfa.resize(trabajo.size, Image.Resampling.BILINEAR)
        return _empaquetar(_quitar_la_figura(alfa, trabajo, boceto), original, guia=imagen)

    trabajo = _reducir(imagen.convert("RGB"), LADO_DE_TRABAJO)
    px = np.asarray(trabajo, dtype=np.float32)
    alto, ancho = px.shape[:2]

    # EL FONDO NO ES UN COLOR: ES UNA SUPERFICIE.
    fondo = _campo_de_fondo(px)

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
    if boceto:
        alcanzado = _fondo_de_boceto(px, alcanzado)

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

    # PASO 3. En una foto, GrabCut: corte de grafo con modelos de color.
    if not boceto:
        mascara = _refinar_con_grabcut(trabajo, mascara, distancia > umbral * FACTOR_DE_COLOR_SEGURO)

    # PASO 4. Sacar a la persona dibujada, si la hay.
    mascara = _quitar_la_figura(mascara, trabajo, boceto)

    return _empaquetar(mascara, original, guia=imagen)


def _campo_de_fondo(px: np.ndarray) -> np.ndarray:
    """El color del fondo EN CADA PUNTO, no uno solo para toda la imagen.

    EL FALLO QUE ARREGLA, Y CÓMO SE ENCONTRÓ
    ----------------------------------------
    El recorte de una fotografía de camiseta incluía un manchón de fondo a su
    derecha, que después salía estampado de tela. Parecía la sombra proyectada
    y no lo era: medido, ese manchón tiene brillo **235 y el fondo 223**. Es
    MÁS CLARO. Era el degradado del ciclorama del estudio.

    Un solo color tomado de las esquinas no puede representar un fondo con
    degradado: en la zona clara la diferencia llegaba a 21, por encima del
    umbral de 18, y el relleno se paraba ahí como si hubiera empezado la
    prenda. El umbral no estaba mal ajustado — **el modelo de fondo estaba mal
    planteado**.

    Un ciclorama, un papel iluminado desde un lado, el viñeteo de un objetivo:
    todos son suaves y de orden bajo. Una superficie cuadrática por canal los
    describe bien, y se aprende del MARCO de la imagen, que es donde con más
    seguridad no hay prenda.

    POR QUÉ EL AJUSTE ES ROBUSTO
    ----------------------------
    Porque una prenda puede tocar el marco. Se ajusta, se miran los residuos, se
    descarta lo que se aparta más de 2,5 desviaciones —medidas con la mediana,
    que no se deja arrastrar— y se vuelve a ajustar. Si queda muy poco donde
    apoyarse, se usa el marco entero: preferible un ajuste mediocre a uno
    dominado por cuatro píxeles.

    LO QUE SE DESCARTÓ, Y POR QUÉ
    -----------------------------
    Frenar el relleno con la fuerza del borde —dejarle pasar por cualquier sitio
    liso— también arreglaba la camiseta. Y se **comía un tercio del vestido**:
    de 0,369 a 0,254 de cobertura con umbral 0,015, porque el interior de un
    dibujo a lápiz también es liso. Entre el valor que funciona (0,008) y el que
    destruye (0,015) hay un factor dos. Es el mismo error que la apertura
    morfológica que se comió la camiseta blanca, y se descartó por lo mismo.
    """
    alto, ancho = px.shape[:2]

    # Coordenadas normalizadas a [-1, 1]: el ajuste no depende del tamaño.
    yy, xx = np.mgrid[0:alto, 0:ancho].astype(np.float32)
    x = (xx / max(ancho - 1, 1)) * 2.0 - 1.0
    y = (yy / max(alto - 1, 1)) * 2.0 - 1.0
    base = np.stack(
        [np.ones_like(x), x, y, x * x, x * y, y * y], axis=-1
    ).reshape(-1, 6)

    grosor = max(2, round(min(alto, ancho) * FRANJA_DEL_MARCO))
    marco = np.zeros((alto, ancho), dtype=bool)
    marco[:grosor, :] = marco[-grosor:, :] = True
    marco[:, :grosor] = marco[:, -grosor:] = True
    marco = marco.reshape(-1)

    campo = np.empty_like(px)
    for canal in range(3):
        valores = px[..., canal].reshape(-1)
        apoyo = marco.copy()
        coeficientes = None
        for _ in range(VUELTAS_DEL_AJUSTE):
            coeficientes, *_ = np.linalg.lstsq(base[apoyo], valores[apoyo], rcond=None)
            residuo = np.abs(valores - base @ coeficientes)
            # 1,4826 convierte la mediana de los residuos en algo comparable a
            # una desviación típica, sin que un valor extremo la infle.
            escala = float(np.median(residuo[apoyo])) * 1.4826 + 1e-3
            siguiente = marco & (residuo <= 2.5 * escala)
            if siguiente.sum() < base.shape[1] * 8:
                break
            apoyo = siguiente
        campo[..., canal] = (base @ coeficientes).reshape(alto, ancho)

    return campo


def _pegar_al_borde(
    mascara: Image.Image, guia: Image.Image, tamano: tuple[int, int]
) -> Image.Image:
    """Decide el borde a tamaño completo con el color de la propia foto.

    DOS PASOS, Y EL PRIMERO ES EL QUE MUEVE EL BORDE
    ------------------------------------------------
    La máscara se calcula a 512 px y hay que llevarla a la foto entera. Solo
    ampliándola, el borde queda donde caía en la imagen pequeña.

    1. **Clasificación local en la franja dudosa.** Alrededor del borde
       ampliado se toma una franja. Justo dentro de ella hay prenda segura, y
       justo fuera, fondo seguro: de ahí se estima el COLOR LOCAL de cada uno,
       con convolución normalizada. Cada píxel de la franja se queda con el
       que más se le parece. Eso sí lleva el borde al contorno real.
    2. **Filtro guiado** (He, Sun y Tang, 2010) para el canto: suave donde la
       foto tiene un canto suave y seco donde lo tiene seco.

    LO QUE SE CREYÓ Y NO ERA VERDAD
    -------------------------------
    La primera versión confiaba el paso 1 al filtro guiado, en dos pasadas, con
    la idea de que la foto le diría dónde está el borde. Una prueba lo
    desmintió: con la máscara pasada 6 px hacia el fondo, el borde quedaba a
    −5; con 8, a −7. El filtro guiado conserva la media de la entrada donde la
    guía es lisa, y la franja entre el borde falso y el real ES fondo liso: no
    tiene de dónde saber que sobra.

    Así que los halos que desaparecieron del banco de pruebas los quitaron
    GrabCut, el modelo de fondo como superficie y el sombreado calculado solo
    con prenda pura — no esto. Esto ajusta los últimos píxeles, que es lo que
    queda por ajustar después de GrabCut.
    """
    import cv2

    ancho, alto = tamano
    color = np.asarray(
        guia.convert("RGB").resize(tamano, Image.Resampling.BILINEAR), dtype=np.float32
    ) / 255.0
    entrada = np.asarray(mascara, dtype=np.float32) / 255.0
    prenda = entrada > 0.5

    escala = max(ancho, alto) / LADO_DE_TRABAJO
    franja = max(2, int(np.ceil(escala * FRANJA_DEL_BORDE)))
    disco = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * franja + 1, 2 * franja + 1))
    segura = cv2.erode(prenda.astype(np.uint8), disco) > 0
    fondo = cv2.dilate(prenda.astype(np.uint8), disco) == 0
    dudosa = ~segura & ~fondo

    if dudosa.any() and segura.any() and fondo.any():
        radio = franja * 3
        color_prenda = _media_local(color, segura, radio)
        color_fondo = _media_local(color, fondo, radio)
        a_prenda = np.linalg.norm(color - color_prenda, axis=2)
        a_fondo = np.linalg.norm(color - color_fondo, axis=2)
        prenda = segura | (dudosa & (a_prenda < a_fondo))

    gris = color @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    fino = max(1, round(escala * 0.75))
    alfa = np.clip(filtro_guiado(gris, prenda.astype(np.float32), fino, EPS_DEL_BORDE), 0.0, 1.0)
    # Lo que queda casi a 0 o casi a 1 es ruido del ajuste, no borde.
    alfa[alfa < 0.03] = 0.0
    alfa[alfa > 0.97] = 1.0
    return Image.fromarray((alfa * 255.0 + 0.5).astype(np.uint8), mode="L")


def _media_local(color: np.ndarray, donde: np.ndarray, radio: int) -> np.ndarray:
    """Color medio de `donde` alrededor de cada píxel (convolución normalizada)."""
    from app.textil.filtros import media_de_caja

    peso = donde.astype(np.float32)
    denominador = np.maximum(media_de_caja(peso, radio), 1e-6)
    return np.stack(
        [media_de_caja(color[..., c] * peso, radio) / denominador for c in range(3)], axis=-1
    )


def _refinar_con_grabcut(
    trabajo: Image.Image, mascara: Image.Image, distinta: np.ndarray
) -> Image.Image:
    """Corrige el recorte con GrabCut: corte de grafo con modelos de color.

    POR QUÉ, CON LAS MEDIDAS DEL BANCO DE PRUEBAS
    ---------------------------------------------
    El relleno desde el borde decide con UN umbral de color, y falla en los dos
    sentidos. Los dos se vieron: a la camiseta blanca sobre fondo gris claro le
    faltaba un trozo del bajo, y a la cazadora de cuero la rodeaba el
    resplandor del fondo del estudio, que entraba como prenda.

    GrabCut (Rother, Kolmogorov y Blake, 2004) aprende una mezcla de gaussianas
    para el color de la prenda y otra para el del fondo, y resuelve un corte de
    grafo que equilibra el color con la continuidad del borde: prefiere cortar
    por donde la foto tiene un borde de verdad. Es el método clásico cuando un
    umbral no basta.

    SE INICIALIZA CON LO QUE YA SE SABE
    -----------------------------------
    Núcleo de la máscara: prenda segura. Resto de la máscara: prenda probable.
    Una banda alrededor: fondo probable, para que pueda CRECER hacia un trozo
    que faltaba. Lo lejano: fondo seguro. Así corrige errores de unos cuantos
    píxeles sin poder inventarse una prenda en otra parte de la foto.

    Y si cambia la cobertura más de lo razonable, se queda con el recorte de
    antes: cuando prenda y fondo tienen colores casi iguales, GrabCut puede
    derrumbarse, y un recorte mediocre es mejor que uno roto.

    «PRENDA SEGURA» EXIGE DOS PRUEBAS
    ---------------------------------
    `distinta` marca los píxeles de color CLARAMENTE distinto del fondo. Con
    solo la geometría —el núcleo de la máscara erosionada— la cazadora de cuero
    seguía con fondo pegado a las mangas: el recorte inicial se pasaba 35 px, y
    lo más hondo de ese halo quedaba marcado como prenda segura, que GrabCut no
    puede corregir. Ahora la prenda segura tiene que estar dentro Y tener otro
    color. El cuero negro lo cumple; el resplandor gris del estudio, no.

    Si casi nada de la prenda es claramente distinto —una camiseta blanca sobre
    gris claro—, no hay en qué apoyarse, y se vuelve al criterio geométrico.
    """
    import cv2

    binaria = np.asarray(mascara, dtype=np.uint8) > 127
    if binaria.mean() < 0.01:
        return mascara

    alto, ancho = binaria.shape
    lado = min(alto, ancho)

    def disco(radio: int) -> np.ndarray:
        return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radio + 1, 2 * radio + 1))

    banda = max(3, round(lado * BANDA_DUDOSA))
    nucleo = cv2.erode(binaria.astype(np.uint8), disco(max(2, round(lado * NUCLEO_SEGURO)))) > 0
    interior = cv2.erode(binaria.astype(np.uint8), disco(max(2, banda // 2))) > 0
    alcance = cv2.dilate(binaria.astype(np.uint8), disco(banda)) > 0

    # TODO EL BORDE DUDOSO EMPIEZA COMO FONDO.
    #
    # La primera versión marcaba la máscara entera como prenda probable. En la
    # cazadora de cuero eso incluía el resplandor del fondo del estudio, y el
    # modelo de color de la prenda —cinco gaussianas— dedicó una a ese gris
    # claro y lo conservó. Es el fallo clásico de GrabCut con una
    # inicialización sesgada. Sin el sesgo, la franja del borde tiene que
    # ganarse ser prenda por su color y por dónde está el borde de verdad.
    marca = np.full((alto, ancho), cv2.GC_BGD, dtype=np.uint8)
    marca[alcance] = cv2.GC_PR_BGD
    if (binaria & distinta).sum() >= PRENDA_DISTINTA_MINIMA * binaria.sum():
        marca[binaria & distinta] = cv2.GC_PR_FGD
        marca[nucleo & distinta] = cv2.GC_FGD
    else:
        marca[interior] = cv2.GC_PR_FGD
        marca[nucleo & interior] = cv2.GC_FGD

    # El marco de la foto es fondo seguro, salvo donde la prenda lo toca: una
    # foto recortada al ras no debe perder la manga.
    m = max(2, round(lado * 0.01))
    marco = np.zeros_like(binaria)
    marco[:m, :] = True
    marco[-m:, :] = True
    marco[:, :m] = True
    marco[:, -m:] = True
    marca[marco & ~binaria] = cv2.GC_BGD

    bgr = np.ascontiguousarray(np.asarray(trabajo.convert("RGB"))[:, :, ::-1])
    fondo_gmm = np.zeros((1, 65), np.float64)
    prenda_gmm = np.zeros((1, 65), np.float64)
    cv2.grabCut(bgr, marca, None, fondo_gmm, prenda_gmm, VUELTAS_DE_GRABCUT, cv2.GC_INIT_WITH_MASK)

    nueva = (marca == cv2.GC_FGD) | (marca == cv2.GC_PR_FGD)
    antes, despues = float(binaria.mean()), float(nueva.mean())
    if not (antes * (1 - CAMBIO_MAXIMO) <= despues <= antes * (1 + CAMBIO_MAXIMO)):
        return mascara

    # Lo que GrabCut deje encerrado dentro también es prenda.
    nueva = ~_rellenar_desde_el_borde(~nueva)
    return Image.fromarray(nueva.astype(np.uint8) * 255, mode="L")


def _quitar_la_figura(
    mascara: Image.Image, trabajo: Image.Image, boceto: bool = False
) -> Image.Image:
    """Quita del recorte la piel y el pelo de la figura, si los hay.

    POR QUÉ HACE FALTA
    ------------------
    El recorte contesta «qué no es fondo», y en un figurín lo que no es fondo
    incluye a la modelo. La tela se le estampaba encima: cara burdeos, pelo
    burdeos, brazos burdeos. Para un producto que promete enseñar TU dibujo con
    otra tela, pintarle la cara a la modelo es cambiar el dibujo.

    CÓMO SE DISTINGUE
    -----------------
    Por saturación. El lápiz con el que se dibuja la prenda es acromático; la
    piel y el pelo se colorean. Hay un orden de magnitud entre las dos cosas
    (0,02 contra 0,10+), así que el umbral no es delicado — ver
    `SATURACION_DE_LA_FIGURA`.

    Y POR QUÉ NO SE FÍA DE ESO A SECAS
    ----------------------------------
    Porque una prenda de color cálido también es saturada. Si lo detectado
    ocupa casi todo el recorte, lo que hay no es una persona: es una prenda de
    color, y no se toca nada. La regla solo puede quitar una minoría.
    """
    ancho, alto = trabajo.size
    px = np.asarray(trabajo.convert("RGB"), dtype=np.float32)
    dentro = np.asarray(mascara.resize((ancho, alto), Image.Resampling.BILINEAR)) > 127
    if not dentro.any():
        return mascara

    maximo = px.max(axis=2)
    minimo = px.min(axis=2)
    saturacion = (maximo - minimo) / np.maximum(maximo, 1.0)

    # Cálido además de saturado: descarta el azulado que deja una sombra de
    # lápiz sobre papel blanco, que también sube algo de saturación.
    # Y con CROMA absoluto, no solo saturación relativa. La saturación divide por
    # el brillo, y en un gris oscuro de grafito con un leve tinte cálido —por
    # ejemplo (60, 52, 50)— sale 0,17: se quitaba un rectángulo del sombreado
    # del vestido como si fuera piel. El pelo y la piel tienen croma de 30 para
    # arriba; el grafito, 10–15.
    figura = (
        (saturacion > SATURACION_DE_LA_FIGURA)
        & ((maximo - minimo) > CROMA_DE_LA_FIGURA)
        & (px[..., 0] > px[..., 2])
        & dentro
    )

    # LO QUE SE PROBÓ PARA LA PIEL PÁLIDA Y NO SIRVIÓ
    #
    # El escote y los hombros de un figurín se pintan en un beige tan pálido que
    # este umbral no los ve (saturación 0,06 frente a 0,10). Se probó añadir un
    # criterio de TONO (10–45°), que en el escote sí separa piel de corpiño. Y
    # agujereaba la falda: su sombreado a lápiz tiene zonas de tinte cálido.
    # Exigir que esa piel estuviera unida a la figura tampoco bastó: el brazo de
    # la modelo baja pegado al vestido y conecta las manchas con el cuerpo.
    #
    # Separar piel y vestido en un dibujo de verdad necesita un modelo aprendido
    # de análisis de personas. Hasta entonces, la tela sobre los hombros
    # desnudos es una limitación conocida; es mejor que un vestido con agujeros.

    lienzo = Image.fromarray(figura.astype(np.uint8) * 255, mode="L")

    # Apertura: quita el fleco de color a lo largo de cada línea de lápiz, que
    # es del escáner y no del dibujo. Aquí erosionar es seguro —justo al revés
    # que sobre la máscara de la prenda— porque lo fino ES el ruido.
    lado = RADIO_LIMPIEZA_DE_FIGURA * 2 + 1
    lienzo = lienzo.filter(ImageFilter.MinFilter(lado)).filter(ImageFilter.MaxFilter(lado))

    # Cierre: une el pelo por encima de la cara, para que la cara quede
    # encerrada y el relleno la pueda tapar.
    lado = RADIO_UNION_DE_FIGURA * 2 + 1
    lienzo = lienzo.filter(ImageFilter.MaxFilter(lado)).filter(ImageFilter.MinFilter(lado))

    # Tapar lo que la figura encierra: la cara es papel en blanco y no tiene
    # color propio que detectar, pero está rodeada de pelo.
    solida = np.asarray(lienzo, dtype=np.uint8) > 127
    solida = ~_rellenar_desde_el_borde(~solida)
    solida &= dentro

    proporcion = solida.sum() / max(1, dentro.sum())
    if proporcion > MAXIMO_DE_FIGURA:
        # No es una persona: es una prenda de color. Ver MAXIMO_DE_FIGURA.
        return mascara

    # Se quita la figura MÁS el margen que el cierre morfológico había hecho
    # crecer a la máscara hacia fuera. Sin esto quedaba un anillo de papel
    # alrededor de la cabeza de la modelo, dentro de la máscara, y la tela lo
    # pintaba: un halo rosa o de rayas rodeando el pelo.
    margen = Image.fromarray(solida.astype(np.uint8) * 255, mode="L").filter(
        ImageFilter.MaxFilter(RADIO_CIERRE * 2 + 3)
    )
    solida = np.asarray(margen, dtype=np.uint8) > 127
    quitada = dentro & ~solida
    return Image.fromarray(quitada.astype(np.uint8) * 255, mode="L").resize(
        mascara.size, Image.Resampling.BILINEAR
    )


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

    Es lo mismo que un recorrido en anchura desde el marco con vecindad de 4,
    hecho con componentes conexas: una componente de `similar` se alcanza desde
    el borde si toca el marco. Antes era un recorrido en Python puro, píxel a
    píxel; bastaba mientras se hacía una vez por imagen, y dejó de bastar
    cuando el boceto pasó a necesitar varios rellenos para buscar su umbral.
    """
    import cv2

    cuantas, etiquetas = cv2.connectedComponents(similar.astype(np.uint8), connectivity=4)
    if cuantas <= 1:
        return np.zeros_like(similar, dtype=bool)
    en_el_marco = np.unique(
        np.concatenate([etiquetas[0], etiquetas[-1], etiquetas[:, 0], etiquetas[:, -1]])
    )
    en_el_marco = en_el_marco[en_el_marco > 0]
    return np.isin(etiquetas, en_el_marco) & similar


def _fondo_de_boceto(px: np.ndarray, por_color: np.ndarray) -> np.ndarray:
    """El fondo de un dibujo: todo lo que se alcanza desde el borde sin cruzar un trazo.

    EL PROBLEMA, Y UNA SOLUCIÓN QUE NO SIRVIÓ
    -----------------------------------------
    Un figurín suele llevar una sombra suave alrededor de la figura. El umbral de
    color se paraba en ella y la sombra entraba en la máscara: un anillo que, al
    quitar el pelo y la piel, se quedaba solo y se pintaba de tela alrededor de
    la cabeza de la modelo.

    Subir el umbral —buscando el último antes de que la cobertura se derrumbara—
    quitaba la sombra (a 32 del papel, frente a 72 del sombreado del vestido),
    pero se colaba por los tramos débiles del contorno y dejaba huecos en las
    zonas claras de la cola. El derrumbe grande se veía; las fugas pequeñas, no.

    LA FRONTERA DE UN DIBUJO ES LA LÍNEA
    ------------------------------------
    En una foto la prenda se separa del fondo por el color; en un dibujo, por la
    línea de lápiz. Así que el relleno puede pasar por todo MENOS por el trazo
    —detectado como en el retexturizado: estrecho y más oscuro que lo que lo
    rodea—, engrosado un píxel para sellar los cortes del contorno. La sombra no
    tiene líneas y se atraviesa entera; el interior queda protegido por su
    contorno aunque sea claro.

    SOLO POR LA FRANJA EXTERIOR
    ---------------------------
    Con la línea como única barrera se colaba casi siempre: el croquis de
    referencia tiene el contorno abierto en varios tramos, y quedaba 0,16–0,22
    de prenda frente a 0,37. Una regla local no puede cerrar un contorno que el
    dibujante dejó abierto. Lo que sí puede es acotar el daño: la sombra es una
    franja de 10–15 px por fuera del contorno, así que el relleno solo avanza
    por la franja exterior de la máscara, `ANCHO_DE_SOMBRA` como mucho. Por un
    corte del contorno entra esos píxeles, no un agujero en media cola.
    """
    import cv2

    brillo = px @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    radio = max(1, round(max(px.shape[:2]) / 256))
    sin_trazo = cv2.dilate(brillo, np.ones((2 * radio + 1, 2 * radio + 1), np.uint8))
    hundido = 1.0 - brillo / np.maximum(sin_trazo, 1.0)
    trazo = (hundido > TRAZO_DE_BARRERA).astype(np.uint8)
    trazo = cv2.dilate(trazo, np.ones((3, 3), np.uint8), iterations=SELLADO_DEL_TRAZO) > 0

    prenda = (~por_color).astype(np.uint8)
    hondura = cv2.distanceTransform(prenda, cv2.DIST_L2, 3)
    franja = (prenda > 0) & (hondura <= ANCHO_DE_SOMBRA)
    return _rellenar_desde_el_borde(por_color | (franja & ~trazo))


def _empaquetar(
    mascara: Image.Image,
    tamano_original: tuple[int, int],
    *,
    forzar_dudoso: bool = False,
    guia: Image.Image | None = None,
) -> Recorte:
    """Devuelve la máscara al tamaño original, con el borde pegado al real, y medida."""
    if mascara.size != tamano_original:
        mascara = mascara.resize(tamano_original, Image.Resampling.BILINEAR)

    if guia is not None:
        mascara = _pegar_al_borde(mascara, guia, tamano_original)
    else:
        # Sin foto de guía (una máscara de relleno total), basta un canto suave.
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
