"""Por dónde corre el hilo de la tela en cada parte de la prenda.

EL PROBLEMA
-----------
Una raya estampada bajaba vertical por toda la imagen, también por una manga
que sale en diagonal. En una prenda de verdad la raya corre A LO LARGO de la
manga, porque la manga se corta aparte con el hilo siguiendo el brazo. Es lo que
más delata el montaje en una tela a rayas o a cuadros — y la tienda tiene cinco
rayas en el catálogo.

CÓMO LO RESUELVEN LOS CONFIGURADORES, Y CÓMO SE RESUELVE AQUÍ
------------------------------------------------------------
Los configuradores de prendas usan un mapa UV hecho a mano por cada foto: un
diseñador marca cada pieza del patrón y cómo corre en ella el hilo. Aquí no hay
diseñador, y las piezas se deducen de la FORMA de la máscara:

1. **Qué es una manga.** Lo que la distingue del cuerpo es el grosor: una manga
   es estrecha comparada con el torso. Se mide el GROSOR LOCAL (Hildebrand y
   Rüegsegger, 1997): en cada punto, el diámetro del mayor círculo inscrito en
   la prenda que lo contiene. Se calcula con la transformada de distancia —sus
   crestas son los centros de esos círculos, y su valor el radio— pintando cada
   círculo de menor a mayor.
2. **Hacia dónde va.** Cada pieza estrecha se analiza por componentes
   principales: el eje de mayor varianza de sus píxeles es el eje de la manga.
3. **Un panel por pieza.** Si la pieza es alargada y su eje se aparta de la
   vertical, se gira entera alrededor de su centro, como una manga cortada
   aparte y cosida. En la costura entre panel y cuerpo la raya cambia de
   ángulo — que es lo que pasa en una camisa de rayas de verdad.
4. Lo demás, vertical: una prenda se fotografía derecha y el hilo del cuerpo
   baja recto.

LO QUE SE PROBÓ ANTES Y NO SIRVIÓ
---------------------------------
El tensor de estructura del gradiente de la distancia. La idea era que en un
tubo todo el gradiente apunta de lado a lado y la dirección sale coherente. Sale
coherente, sí — pero también junto a CUALQUIER borde recto: el bajo de una
camiseta daba una "pieza" horizontal, y la prenda se llenaba de rayas en U. La
coherencia mide que haya un borde dominante, no que haya una manga.
"""

from __future__ import annotations

import numpy as np

#: Lado al que se reduce la máscara para calcular la veta. La dirección de una
#: manga no necesita resolución completa, y la transformada de distancia sí
#: cuesta.
LADO_DE_LA_VETA = 320

#: Una pieza es "estrecha" —manga, pernera, tirante— si su grosor local no pasa
#: de esta fracción del grosor máximo de la prenda (el del torso).
PIEZA_ESTRECHA = 0.55

#: QUÉ ES UNA MANGA, MEDIDO EN EL BANCO DE PRUEBAS
#:
#: Todas las piezas estrechas de cinco prendas, con su alargamiento (raíz del
#: cociente de varianzas de sus ejes), su ángulo respecto a la vertical y su
#: área:
#:
#: - Mangas cortas de las dos camisetas: alargamiento 3,1–3,5, ángulo 13–27°,
#:   área 6,5–8%. Son las que hay que girar.
#: - Franjas de hombro de la cazadora y el jersey: ángulo ~90°. Una manga no
#:   sale nunca horizontal; una franja pegada a los hombros, sí.
#: - Esquinas del bajo y puños: alargamiento 1,4–2,2, casi tan anchos como
#:   largos, así que su eje no dice nada.
#:
#: Se descartó antes medir qué parte del contorno de la pieza toca el torso: las
#: mangas daban 0,42–0,50 y los hombros 0,45–0,53. No separa.
#:
#: Las mangas LARGAS pegadas al cuerpo no se pueden aislar por la forma: en la
#: máscara se funden con el torso. Pero cuelgan casi verticales, y la raya
#: vertical ya es aproximadamente la suya.
ALARGAMIENTO_MINIMO = 2.5
ANGULO_MINIMO = np.radians(10)
ANGULO_MAXIMO = np.radians(60)

#: Tamaño mínimo de un panel, en fracción de la prenda.
PANEL_MINIMO = 0.03


def coordenadas_de_la_veta(alfa: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
    """Coordenadas de textura (x, y) que siguen la veta de cada pieza.

    Devuelve dos campos del tamaño de `alfa` y el número de paneles girados. Con
    cero paneles, las coordenadas son las de la imagen tal cual.
    """
    import cv2

    alto, ancho = alfa.shape
    x = np.broadcast_to(np.arange(ancho, dtype=np.float32)[None, :], (alto, ancho)).copy()
    y = np.broadcast_to(np.arange(alto, dtype=np.float32)[:, None], (alto, ancho)).copy()

    binaria = alfa > 0.5
    if binaria.sum() < 256:
        return x, y, 0

    escala = min(1.0, LADO_DE_LA_VETA / max(alto, ancho))
    pequeno = cv2.resize(
        binaria.astype(np.uint8), (max(8, round(ancho * escala)), max(8, round(alto * escala))),
        interpolation=cv2.INTER_NEAREST,
    )
    grosor = grosor_local(pequeno)
    dentro = pequeno > 0
    maximo = float(grosor[dentro].max()) if dentro.any() else 0.0
    if maximo <= 0:
        return x, y, 0

    estrecha = (dentro & (grosor <= PIEZA_ESTRECHA * maximo)).astype(np.uint8)
    estrecha = cv2.morphologyEx(
        estrecha, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    )
    cuantas, etiquetas = cv2.connectedComponents(estrecha, connectivity=8)

    area_prenda = float(dentro.sum())
    paneles = 0
    etiquetas_panel = np.zeros_like(etiquetas)
    giros: dict[int, tuple[float, float, float]] = {}
    for k in range(1, cuantas):
        pieza = etiquetas == k
        filas, columnas = np.nonzero(pieza)
        if filas.size < PANEL_MINIMO * area_prenda:
            continue
        giro, alargamiento = _eje_principal(columnas.astype(np.float64), filas.astype(np.float64))
        if alargamiento < ALARGAMIENTO_MINIMO or not (ANGULO_MINIMO <= abs(giro) <= ANGULO_MAXIMO):
            continue
        paneles += 1
        etiquetas_panel[etiquetas == k] = paneles
        giros[paneles] = (giro, float(columnas.mean()) / escala, float(filas.mean()) / escala)

    if not paneles:
        return x, y, 0

    # Las etiquetas se amplían por vecino más próximo: un panel no tiene bordes
    # suaves, tiene una costura.
    etiquetas_reales = cv2.resize(
        etiquetas_panel.astype(np.float32), (ancho, alto), interpolation=cv2.INTER_NEAREST
    ).astype(np.int32)

    for k, (giro, cx, cy) in giros.items():
        region = etiquetas_reales == k
        dx, dy = x[region] - cx, y[region] - cy
        coseno, seno = np.cos(giro), np.sin(giro)
        # A lo largo del eje de la pieza corre el eje vertical del mosaico, que
        # es por donde corren sus rayas.
        x[region] = cx + dx * coseno - dy * seno
        y[region] = cy + dx * seno + dy * coseno

    return x, y, paneles


def grosor_local(binaria: np.ndarray) -> np.ndarray:
    """Diámetro del mayor círculo inscrito que contiene cada punto.

    Las crestas de la transformada de distancia son centros de círculos
    inscritos máximos, y su valor el radio. Pintando cada círculo con su radio,
    de menor a mayor, cada píxel se queda con el mayor que lo cubre.
    """
    import cv2

    distancia = cv2.distanceTransform(binaria.astype(np.uint8), cv2.DIST_L2, 5)
    vecindad = cv2.dilate(distancia, np.ones((3, 3), np.uint8))
    cresta = (distancia >= vecindad - 1e-6) & (distancia > 1.0)

    filas, columnas = np.nonzero(cresta)
    radios = distancia[filas, columnas]
    orden = np.argsort(radios)
    lienzo = np.zeros(binaria.shape, dtype=np.float32)
    for i in orden:
        r = float(radios[i])
        cv2.circle(lienzo, (int(columnas[i]), int(filas[i])), int(round(r)), 2.0 * r, thickness=-1)
    return lienzo * (binaria > 0)


def _eje_principal(xs: np.ndarray, ys: np.ndarray) -> tuple[float, float]:
    """Ángulo del eje mayor respecto a la vertical, y cuánto más largo es que ancho."""
    cx, cy = xs.mean(), ys.mean()
    covarianza = np.cov(np.stack([xs - cx, ys - cy]))
    valores, vectores = np.linalg.eigh(covarianza)
    mayor = vectores[:, int(np.argmax(valores))]
    angulo = float(np.arctan2(mayor[0], mayor[1]))  # respecto a la vertical (0, 1)
    # Una veta es una recta, no un sentido: se dobla a (−90°, 90°].
    if angulo > np.pi / 2:
        angulo -= np.pi
    elif angulo <= -np.pi / 2:
        angulo += np.pi
    alargamiento = float(np.sqrt(max(valores.max(), 1e-9) / max(valores.min(), 1e-9)))
    return angulo, alargamiento
