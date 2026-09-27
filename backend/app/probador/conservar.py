"""Qué parte de la imagen generada se queda, y qué vuelve a ser la foto original.

LA REGLA
--------
Del modelo se toma la ropa que se está probando, y la piel que esa ropa nueva
destapa o tapa. Todo lo demás —cara, pelo, manos que no cambian, el resto de
la ropa, el fondo— son los píxeles ORIGINALES de la foto, a su resolución.

Es la misma idea que el bloqueo estructural de las pruebas de tela: no se le
pide al modelo que respete algo, se le impide tocarlo. Y hace falta por lo que
se midió con salidas reales (ver `partes.py`): el modelo regenera una caja
entera alrededor del torso e inventa dentro de ella.

LA ZONA, PASO A PASO
--------------------
1. **Ropa de la categoría**, en la foto original Y en la generada. En la
   original, porque la prenda vieja tiene que desaparecer aunque la nueva sea
   más pequeña; en la generada, porque la nueva puede ser más grande.
2. **Piel de la categoría** —brazos para una camisa, piernas para una falda—
   solo donde la imagen cambió: una manga corta nueva destapa brazo que antes
   cubría una manga larga, y ese brazo lo tiene que poner el modelo. Un brazo
   que no cambia se queda con sus píxeles originales.
3. Se limpian las islas que el analizador deja sueltas, se ensancha un margen
   para llevarse el canto de la prenda y su sombra, y se difumina para que la
   costura entre imagen generada y foto no se vea.

Lo que NO entra aunque cambie: la cara, el pelo, el fondo, los zapatos, el
bolso y, en una camisa, el pantalón. Si el modelo los cambió, se deshace, y
se cuenta: es el `descartado` que acaba en el aviso de la prueba.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.models.try_on import GarmentCategory
from app.probador import partes as P

#: Qué ropa sustituye cada categoría. El vestido entra en todas: si la persona
#: lleva uno y se prueba una camisa, la parte de arriba del vestido tiene que
#: poder desaparecer.
ROPA = {
    GarmentCategory.TOP: {P.ROPA_ARRIBA, P.VESTIDO, P.BUFANDA},
    GarmentCategory.BOTTOM: {P.FALDA, P.PANTALON, P.VESTIDO, P.CINTURON},
    GarmentCategory.FULL: {P.ROPA_ARRIBA, P.FALDA, P.PANTALON, P.VESTIDO, P.CINTURON, P.BUFANDA},
}

#: Qué piel puede destapar o tapar cada categoría.
PIEL = {
    GarmentCategory.TOP: {P.BRAZO_IZQ, P.BRAZO_DER},
    GarmentCategory.BOTTOM: {P.PIERNA_IZQ, P.PIERNA_DER},
    GarmentCategory.FULL: {P.BRAZO_IZQ, P.BRAZO_DER, P.PIERNA_IZQ, P.PIERNA_DER},
}

#: Diferencia de color (sRGB, distancia euclídea sobre 255, tras un
#: desenfoque suave) a partir de la cual un píxel "ha cambiado". Medido en dos
#: salidas reales: lo que el modelo deja igual —la cara, el fondo lejano— se
#: queda en 2–6 de mediana; la prenda nueva pasa de 50.
UMBRAL_DE_CAMBIO = 25.0

#: Margen alrededor de la zona, en fracción del alto: el canto de la prenda y
#: la sombra que proyecta sobre el cuerpo. Y el difuminado de la costura.
MARGEN = 0.006
PLUMA = 0.003

#: Islas de zona más pequeñas que esto (fracción de la imagen) son ruido del
#: analizador, no ropa.
ISLA_MINIMA = 0.0005


@dataclass(frozen=True)
class Zona:
    #: De 0 a 1: cuánto de la imagen generada entra en cada píxel.
    alfa: np.ndarray
    #: Fracción de la imagen en la que el analizador ve la prenda nueva. Si es
    #: casi cero, el modelo no ha puesto la prenda.
    prenda_nueva: float
    #: Fracción de la imagen que el modelo cambió FUERA de la zona y se ha
    #: devuelto a la foto original.
    descartado: float


def zona_editable(
    persona: np.ndarray,
    generada: np.ndarray,
    partes_persona: np.ndarray,
    partes_generada: np.ndarray,
    categoria: GarmentCategory,
) -> Zona:
    """Calcula la zona que se toma de la imagen generada.

    Las cuatro matrices tienen el mismo alto y ancho: las dos imágenes en RGB
    de 0 a 255 y sus etiquetas de `partes.etiquetar`.
    """
    import cv2

    alto, ancho = partes_persona.shape
    lado = max(alto, ancho)

    suave_p = cv2.GaussianBlur(persona.astype(np.float32), (0, 0), 1.2)
    suave_g = cv2.GaussianBlur(generada.astype(np.float32), (0, 0), 1.2)
    cambio = np.linalg.norm(suave_g - suave_p, axis=2) > UMBRAL_DE_CAMBIO

    ropa = list(ROPA[categoria])
    piel = list(PIEL[categoria])
    nueva = np.isin(partes_generada, ropa)
    zona = np.isin(partes_persona, ropa) | nueva
    zona |= (np.isin(partes_persona, piel) | np.isin(partes_generada, piel)) & cambio

    # Islas sueltas fuera: el analizador deja motas en fondos con textura.
    cuantas, etiquetas, stats, _ = cv2.connectedComponentsWithStats(zona.astype(np.uint8), 8)
    minima = ISLA_MINIMA * alto * ancho
    grandes = np.zeros(cuantas, dtype=bool)
    grandes[1:] = stats[1:, cv2.CC_STAT_AREA] >= minima
    zona = grandes[etiquetas]

    margen = max(2, round(MARGEN * lado))
    disco = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * margen + 1, 2 * margen + 1))
    ancha = cv2.dilate(zona.astype(np.uint8), disco).astype(np.float32)
    alfa = cv2.GaussianBlur(ancha, (0, 0), max(1.0, PLUMA * lado))
    # El núcleo va entero: el difuminado solo suaviza el borde exterior.
    alfa = np.maximum(alfa, zona.astype(np.float32))

    return Zona(
        alfa=np.clip(alfa, 0.0, 1.0),
        prenda_nueva=float(nueva.mean()),
        descartado=float((cambio & (alfa < 0.5)).mean()),
    )
