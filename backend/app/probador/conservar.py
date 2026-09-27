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
   más pequeña; en la generada, porque la nueva puede ser más grande. Con eso
   ya entra la piel que la prenda nueva destapa (era ropa en la foto) o tapa
   (es ropa en la generada).
2. **Lo que es prenda vieja aunque el analizador no lo vea**: un pliegue de
   manga bajo el codo, en sombra, que sale como «brazo» o «fondo». Se añade si
   tiene el color de la prenda vieja de al lado y está pegado a ella.
3. Se limpian las islas que el analizador deja sueltas, se ensancha un margen
   para llevarse el canto de la prenda y su sombra, y se difumina para que la
   costura entre imagen generada y foto no se vea.

LA PIEL NO ENTRA PORQUE HAYA CAMBIADO
-------------------------------------
Así era al principio: los brazos entraban donde la imagen generada fuera
distinta. Una prueba real lo desmintió: el modelo redibujó la mano que
sujetaba el móvil, cortó el móvil y dejó un borrón beige cruzándolo, y todo
eso pasó al resultado porque «había cambiado». Un brazo que es piel en las
dos imágenes no tiene nada que cambiar; si el modelo lo cambia, es un error
del modelo, y se queda el de la foto.

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

#: Dónde puede estar la prenda vieja que el analizador no reconoce: SOLO en lo
#: que etiqueta como fondo. En la foto del usuario frente al espejo, el pliegue
#: de la camiseta negra bajo el codo salió como fondo en 317 de sus 322
#: píxeles. Se probó dejarla crecer también sobre los brazos, y en la foto del
#: hombre sentado se llevaba trozos del antebrazo tatuado.
PUEDE_SER_PRENDA_VIEJA = {P.FONDO}

#: Cuánto se parece al color de la prenda vieja de al lado (distancia RGB
#: sobre 255) y a qué distancia de ella puede estar (fracción del lado mayor).
#: Medido en ese pliegue, a 1024 px: 7,5 de distancia de color de mediana, y
#: entre 25 y 42 px de la parte que el analizador sí reconoce. Con 0,045 (46
#: px) queda cubierto el 94%; con 0,03, solo el 56%. En las otras dos fotos
#: de prueba añade un 0,4% de la prenda, píxeles sueltos del canto.
COLOR_DE_PRENDA_VIEJA = 30.0
ALCANCE_DE_PRENDA_VIEJA = 0.045

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
    nueva = np.isin(partes_generada, ropa)
    vieja = np.isin(partes_persona, ropa)
    vieja |= _prenda_vieja_sin_etiqueta(persona, partes_persona, vieja, lado)
    zona = vieja | nueva

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


def _prenda_vieja_sin_etiqueta(
    persona: np.ndarray, partes: np.ndarray, vieja: np.ndarray, lado: int
) -> np.ndarray:
    """La prenda vieja que el analizador etiquetó como fondo o piel.

    Tres condiciones a la vez: una etiqueta donde puede esconderse
    (`PUEDE_SER_PRENDA_VIEJA`), el color de la prenda vieja DE AL LADO —su
    media local, así una camiseta de rayas sirve igual que una lisa—, y estar
    unida a la parte reconocida sin salir de su alcance.
    """
    import cv2

    from app.textil.filtros import media_de_caja

    if not vieja.any():
        return np.zeros_like(vieja)

    radio = max(3, round(ALCANCE_DE_PRENDA_VIEJA * lado))
    peso = media_de_caja(vieja.astype(np.float32), radio)
    color = np.stack(
        [media_de_caja(persona[..., c] * vieja, radio) for c in range(3)], axis=-1
    ) / np.maximum(peso, 1e-6)[..., None]
    candidata = (
        np.isin(partes, list(PUEDE_SER_PRENDA_VIEJA))
        & (peso > 0.01)
        & (np.linalg.norm(persona - color, axis=2) < COLOR_DE_PRENDA_VIEJA)
    )
    # Solo lo que toca la prenda reconocida: se crece desde ella a través de
    # las candidatas, y lo que queda suelto no cuenta.
    cuantas, etiquetas = cv2.connectedComponents((candidata | vieja).astype(np.uint8), connectivity=8)
    unidas = np.zeros(cuantas, dtype=bool)
    unidas[np.unique(etiquetas[vieja])] = True
    unidas[0] = False
    return unidas[etiquetas] & candidata
