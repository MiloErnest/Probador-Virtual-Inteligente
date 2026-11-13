"""Qué parte de la imagen generada se queda, y qué vuelve a ser la foto original.

LA REGLA
--------
Del modelo se toma la ropa que se está probando, y la piel que esa ropa nueva
destapa o tapa. Todo lo demás —cara, pelo, manos que no cambian, el resto de
la ropa, el fondo— son los píxeles ORIGINALES de la foto, a su resolución.

Es la misma idea que el bloqueo estructural de las pruebas de tela: no se le
pide al modelo que respete algo, se le impide tocarlo. Y hace falta por lo que
se midió con salidas reales (ver `partes.py`): el modelo regenera la imagen
entera e inventa dentro de ella.

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

LA ROPA QUE EL MODELO SE INVENTA TAMPOCO ENTRA
----------------------------------------------
Medido el 10/11/2026 con una camiseta roja de manga corta: con la semilla 66
el modelo le puso debajo unas mangas largas verdes, en sus dos modos y con 30
y con 50 pasos; con la semilla 70, no. Para el analizador esas mangas «son
ropa», y la regla de arriba las dejaba pasar encima de los brazos.

Lo que las delata es el color: no es ninguno de los de la prenda. Medido en
seis salidas reales, con la distancia a la paleta de la prenda en Lab (la luz
pesa poco, porque un pliegue en sombra es la misma tela): en las prendas bien
puestas el 99% de los píxeles queda por debajo de 18; las mangas inventadas,
entre 40 y 65. Donde esa ropa inventada tapaba piel o fondo, vuelve la foto;
donde estaba la prenda vieja no hay nada mejor que poner, se queda, y se
cuenta para avisar de que conviene pedir otra variante.

Con una salvaguarda, como la de la figura en los bocetos: si «inventado» es
más de la mitad de la prenda, no son partes de más, es que la luz de la foto
ha teñido la prenda entera. Entonces no se quita nada.

EL BRAZO QUE EL MODELO DEJA AL AIRE CONSERVA SU ANCHO
-----------------------------------------------------
El modelo dibuja a la persona más delgada de lo que es. Medido el 12/11/2026
con un hombre musculoso y una camiseta de manga corta (prueba 30): el
antebrazo que pinta el modelo tiene el borde de fuera donde el de la foto,
pero es mucho más fino, y el sitio que deja libre por dentro lo ocupa la
camiseta. La regla del paso 1 —la ropa de la imagen generada entra aunque
tape piel— está pensada para una manga larga que cubre el brazo, y aquí hacía
que el cuerpo de la camiseta se comiera media anchura del antebrazo real: en
el resultado «le habíamos quitado masa muscular».

Lo que distingue una manga de eso es el corte del brazo: si en ese tramo —a
lo largo del brazo— la imagen generada enseña piel, el modelo ha dejado el
brazo al aire ahí, y lo que es brazo en la foto se queda entero. Si en ese
tramo no enseña piel, lo ha tapado una manga, y entra la manga. El corte
entre una cosa y otra sigue el dobladillo que dibujó el modelo: cortando en
perpendicular al brazo quedaba una cuña de piel metida en la manga. Un brazo
doblado se parte en dos para que el eje no cruce el codo en diagonal.

Se probó antes otra idea, y se descartó midiéndola: deformar la imagen del
modelo hasta hacer coincidir su silueta con la de la foto. El contorno
exterior casi no se mueve (0,6 px de media); la diferencia está dentro.

Solo los brazos. Una falda sí puede caer por delante de media pierna.

EL FONDO NO SE TOMA NUNCA DEL MODELO
------------------------------------
El modelo regenera el fondo, y no le sale igual: en la foto de un hombre en el
campo cambió la línea de árboles por un horizonte más claro. Dos defectos
venían de ahí, y los dos eran NUESTROS, no del modelo:

- un «fantasma» claro junto al hombro: la camiseta vieja era más ancha que la
  nueva, y lo que asomaba se rellenaba con el fondo del modelo;
- un ribete claro por todo el canto de la prenda: el margen del paso 3 se
  llevaba una tira de ese fondo.

Ahora, donde la imagen generada enseña fondo, se pone el fondo de la FOTO:
tal cual donde se conoce, y prolongado desde los píxeles de fondo más
cercanos donde lo tapaba la prenda vieja (`_extender`). Es borroso si el
hueco es grande, pero tiene los colores de la foto y no inventa nada.

«Enseña fondo» exige tres cosas a la vez, porque el analizador etiqueta como
fondo cosas que no lo son: en la chaqueta corta, parte del abdomen que queda
al aire salió como fondo. Tiene que estar etiquetado como fondo, tener el
color del fondo del modelo de alrededor, y estar unido al fondo de fuera.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

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

# --- La ropa inventada ------------------------------------------------------

#: En cuántos colores se resume la prenda, y qué parte mínima de ella tiene
#: que ocupar uno para contar. Ocho bastan para un estampado: lo que importa
#: no es reproducirlo, es saber qué colores NO tiene.
COLORES_DE_LA_PRENDA = 8
PARTE_MINIMA_DE_UN_COLOR = 0.02

#: Por encima de esto (de 0 a 255, el menor de los tres canales), un píxel de
#: la imagen de la prenda es el blanco sobre el que se manda, no prenda.
BLANCO_DEL_FONDO = 240.0

#: Cuánto pesa la luminosidad al comparar con la paleta. Poco: un pliegue en
#: sombra es la misma tela más oscura.
PESO_DE_LA_LUZ = 0.3

#: Distancia a la paleta (Lab) a partir de la cual esa ropa no es la prenda.
#: Ver la cabecera: 18 de percentil 99 en las buenas, 40–65 en lo inventado.
LEJOS_DE_LA_PRENDA = 30.0

#: Una mancha inventada más pequeña que esto (fracción de la imagen) no se
#: toca: son cantos y sombras, no una manga.
INVENTADO_MINIMO = 0.003

#: Si lo «inventado» pasa de esta parte de la prenda nueva, no son partes de
#: más: es la prenda entera con otra luz. No se quita nada.
INVENTADO_MAXIMO = 0.5

# --- Los brazos al aire -------------------------------------------------------

#: Un brazo generado más pequeño que esto (fracción de la imagen) no se mira.
BRAZO_MINIMO = 0.002

#: Parte del brazo que dibuja el modelo que tiene que caer sobre el brazo de la
#: foto para compararlos. Si no, el modelo lo ha puesto en otro sitio.
BRAZO_COMUN_MINIMO = 0.3

#: Largo entre ancho por debajo del cual un brazo está doblado y se parte en
#: dos antes de buscarle el eje. Un brazo estirado da 3 o más.
BRAZO_RECTO = 2.5

#: Huecos más cortos que esto a lo largo del brazo (fracción del lado mayor)
#: no son un tramo tapado: son el analizador dudando.
TRAMO_MINIMO = 0.015

# --- El fondo ---------------------------------------------------------------

#: Distancia de color (RGB sobre 255) al fondo del modelo de alrededor por
#: debajo de la cual un píxel etiquetado como fondo lo es de verdad. Medido
#: en cuatro salidas reales: el hueco que deja la prenda vieja queda entre 4 y
#: 15 de mediana; la piel del abdomen que el analizador etiquetó como fondo,
#: en 73 de mediana, y su percentil 5 es 46.
COLOR_DE_FONDO = 40.0

#: Cuánto se aleja del canto de la persona el fondo del que se fía, en
#: fracción del lado mayor: el canto de una camiseta negra, mal etiquetado,
#: mancharía el relleno.
BORDE_DEL_FONDO = 0.004

#: Y cuánto se aleja de la prenda VIEJA, que es de donde viene la mancha: su
#: canto y la sombra que proyecta, que el analizador deja como fondo. Medido
#: con una camiseta negra: con 0,004 el hueco del hombro salía gris oliva,
#: oscurecido por ese canto; con 0,012, del color del campo de detrás.
SOMBRA_DE_LA_PRENDA_VIEJA = 0.012

#: Cuánto se mete el fondo de la foto en el canto de la prenda nueva, en
#: fracción del lado mayor. Medido en la camiseta roja contra los árboles:
#: sin esto queda un filo claro de uno o dos píxeles; con 0,002 (2 px a 1024)
#: casi no se ve, y con 0,003 desaparece del todo pero adelgaza más lo fino.
#: Solo actúa donde la prenda limita con fondo: un tirante sobre el hombro
#: limita con piel y no se toca.
CANTO_DE_LA_PRENDA = 0.002

#: Pasillos más estrechos que el doble de esto (fracción del lado mayor) no
#: comunican un hueco de la figura con el fondo de fuera. Ver `_solida`.
CIERRE_DE_LA_FIGURA = 0.02

#: La piel de la imagen generada, para no confundirla con una pared clara.
PIEL = {P.CARA, P.BRAZO_IZQ, P.BRAZO_DER, P.PIERNA_IZQ, P.PIERNA_DER}
PIEL_MINIMA = 0.002

#: Radio, en píxeles, con el que el relleno mira a su alrededor.
RADIO_DEL_RELLENO = 5

#: Menos fondo que esto en la imagen (fracción), y no hay de dónde prolongarlo.
FONDO_MINIMO = 0.01


@dataclass(frozen=True)
class Zona:
    #: De 0 a 1: cuánto de cada píxel deja de ser la foto original.
    alfa: np.ndarray
    #: De 0 a 1: de eso, cuánto es fondo de la foto reconstruido (`fondo`) en
    #: vez de imagen generada.
    relleno: np.ndarray
    #: El fondo de la foto, prolongado por debajo de la persona. `None` si la
    #: foto casi no tiene fondo.
    fondo: np.ndarray | None
    #: Fracción de la imagen en la que el analizador ve la prenda nueva. Si es
    #: casi cero, el modelo no ha puesto la prenda.
    prenda_nueva: float
    #: Fracción de la imagen que el modelo cambió FUERA de la zona y se ha
    #: devuelto a la foto original.
    descartado: float
    #: Fracción de la imagen con ropa que el modelo pintó y no es de la prenda.
    inventado: float = 0.0
    #: Cuánto de la última fila de la imagen es prenda nueva: si es mucho, la
    #: prenda sigue por debajo del cuadro que se le dio al modelo.
    prenda_al_pie: float = 0.0
    #: Fracción de la imagen en la que la prenda tapaba de lado un brazo al
    #: aire y se ha devuelto el brazo de la foto.
    brazo_devuelto: float = 0.0


def paleta_de(prenda: Image.Image) -> np.ndarray | None:
    """Los colores de la prenda, en Lab. `None` si no se distinguen del blanco.

    `prenda` es la que se le manda al modelo: sobre blanco. Una prenda blanca
    no se distingue de ese blanco, y entonces no hay paleta ni comprobación:
    es preferible no comprobar a quitarle a alguien media camisa.
    """
    import cv2

    pequena = prenda.convert("RGB")
    pequena.thumbnail((256, 256), Image.Resampling.BILINEAR)
    px = np.asarray(pequena, dtype=np.float32)
    es_prenda = px.min(axis=2) < BLANCO_DEL_FONDO
    if es_prenda.mean() < 0.02 or es_prenda.sum() < 4 * COLORES_DE_LA_PRENDA:
        return None

    muestras = np.ascontiguousarray(_lab(px)[es_prenda], dtype=np.float32)
    # Agrupar es aleatorio; con la semilla fija, la misma prenda da siempre la
    # misma paleta y la misma prueba, el mismo resultado.
    cv2.setRNGSeed(0)
    criterio = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    _, grupos, centros = cv2.kmeans(
        muestras, COLORES_DE_LA_PRENDA, None, criterio, 3, cv2.KMEANS_PP_CENTERS
    )
    parte = np.bincount(grupos.ravel(), minlength=COLORES_DE_LA_PRENDA) / len(muestras)
    return centros[parte >= PARTE_MINIMA_DE_UN_COLOR]


def zona_editable(
    persona: np.ndarray,
    generada: np.ndarray,
    partes_persona: np.ndarray,
    partes_generada: np.ndarray,
    categoria: GarmentCategory,
    paleta: np.ndarray | None = None,
) -> Zona:
    """Calcula la zona que deja de ser la foto original.

    Las cuatro matrices tienen el mismo alto y ancho: las dos imágenes en RGB
    de 0 a 255 y sus etiquetas de `partes.etiquetar`. `paleta` es la de
    `paleta_de`; sin ella no se busca ropa inventada.
    """
    import cv2

    alto, ancho = partes_persona.shape
    lado = max(alto, ancho)

    persona = persona.astype(np.float32)
    suave_p = cv2.GaussianBlur(persona, (0, 0), 1.2)
    suave_g = cv2.GaussianBlur(generada.astype(np.float32), (0, 0), 1.2)
    cambio = np.linalg.norm(suave_g - suave_p, axis=2) > UMBRAL_DE_CAMBIO

    ropa = list(ROPA[categoria])
    nueva = np.isin(partes_generada, ropa)
    vieja = np.isin(partes_persona, ropa)
    vieja |= _prenda_vieja_sin_etiqueta(persona, partes_persona, vieja, lado)

    # La ropa que no es de la prenda: fuera donde tapaba piel o fondo.
    inventada = _ropa_inventada(suave_g, nueva, paleta, lado)
    # Y la ropa que tapa de lado un brazo que el modelo dejó al aire.
    al_aire = _brazos_al_aire(partes_persona, partes_generada, lado) & nueva
    sobra = (inventada & ~vieja) | al_aire
    zona = vieja | (nueva & ~sobra)

    # Islas sueltas fuera: el analizador deja motas en fondos con textura.
    cuantas, etiquetas, stats, _ = cv2.connectedComponentsWithStats(zona.astype(np.uint8), 8)
    minima = ISLA_MINIMA * alto * ancho
    grandes = np.zeros(cuantas, dtype=bool)
    grandes[1:] = stats[1:, cv2.CC_STAT_AREA] >= minima
    zona = grandes[etiquetas]

    margen = max(2, round(MARGEN * lado))
    disco = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * margen + 1, 2 * margen + 1))
    ancha = cv2.dilate(zona.astype(np.uint8), disco).astype(bool) & ~sobra
    alfa = cv2.GaussianBlur(ancha.astype(np.float32), (0, 0), max(1.0, PLUMA * lado))
    if sobra.any():
        # El difuminado no puede meter en la foto el canto de lo inventado.
        alfa = np.minimum(alfa, 1.0 - cv2.GaussianBlur(sobra.astype(np.float32), (0, 0), 1.0))
    # El núcleo va entero: el difuminado solo suaviza el borde exterior.
    alfa = np.clip(np.maximum(alfa, zona.astype(np.float32)), 0.0, 1.0)

    relleno, fondo = _fondo_de_la_foto(
        persona, suave_g, partes_persona, partes_generada, vieja, lado
    )

    pie = max(1, round(0.01 * alto))
    return Zona(
        alfa=alfa,
        relleno=relleno,
        fondo=fondo,
        prenda_nueva=float(nueva.mean()),
        descartado=float((cambio & (alfa < 0.5)).mean()),
        inventado=float(inventada.mean()),
        brazo_devuelto=float(al_aire.mean()),
        prenda_al_pie=float((nueva & ~inventada)[-pie:].mean()),
    )


def _lab(rgb: np.ndarray) -> np.ndarray:
    """De RGB (0–255) a CIE Lab: L de 0 a 100, a y b en torno a cero."""
    import cv2

    return cv2.cvtColor(np.ascontiguousarray(rgb, dtype=np.float32) / 255.0, cv2.COLOR_RGB2LAB)


def _ropa_inventada(
    generada: np.ndarray, nueva: np.ndarray, paleta: np.ndarray | None, lado: int
) -> np.ndarray:
    """La ropa de la imagen generada que no tiene ningún color de la prenda.

    Solo manchas con cuerpo: una apertura quita los cantos y las sombras
    finas, y lo que queda tiene que ser más grande que `INVENTADO_MINIMO`.
    """
    import cv2

    nada = np.zeros_like(nueva)
    if paleta is None or len(paleta) == 0 or not nueva.any():
        return nada

    lab = _lab(generada)
    peso = np.array([PESO_DE_LA_LUZ, 1.0, 1.0], dtype=np.float32)
    distancia = np.full(nueva.shape, np.inf, dtype=np.float32)
    for color in paleta:
        distancia = np.minimum(distancia, np.linalg.norm((lab - color) * peso, axis=2))
    lejos = (nueva & (distancia > LEJOS_DE_LA_PRENDA)).astype(np.uint8)

    radio = max(1, round(0.003 * lado))
    disco = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radio + 1, 2 * radio + 1))
    lejos = cv2.morphologyEx(lejos, cv2.MORPH_OPEN, disco)
    cuantas, etiquetas, stats, _ = cv2.connectedComponentsWithStats(lejos, 8)
    grandes = np.zeros(cuantas, dtype=bool)
    grandes[1:] = stats[1:, cv2.CC_STAT_AREA] >= INVENTADO_MINIMO * lejos.size
    inventada = grandes[etiquetas]

    if inventada.sum() > INVENTADO_MAXIMO * nueva.sum():
        return nada
    return inventada


def _brazos_al_aire(
    partes_persona: np.ndarray, partes_generada: np.ndarray, lado: int
) -> np.ndarray:
    """Lo que es brazo en la foto en los tramos que la imagen generada deja al aire.

    Ver la cabecera. Devuelve los píxeles de brazo de la foto que tienen que
    quedarse como están aunque la imagen generada pinte ropa encima.

    El eje se le busca al brazo DE LA IMAGEN GENERADA, no al de la foto. Se
    hizo primero al revés y salió torcido: lo que asoma del brazo de la foto
    puede ser un tramo corto y grueso —el bíceps bajo la manga vieja—, sin
    dirección clara, mientras que el brazo que dibuja el modelo es largo y
    fino. Y es en él donde está el dobladillo por el que hay que cortar.
    """
    import cv2

    brazos = [P.BRAZO_IZQ, P.BRAZO_DER]
    en_foto = np.isin(partes_persona, brazos)
    en_generada = np.isin(partes_generada, brazos)
    al_aire = np.zeros(partes_persona.shape, dtype=bool)
    if not (en_foto & en_generada).any():
        return al_aire

    hueco = max(1.0, TRAMO_MINIMO * lado)
    minimo = BRAZO_MINIMO * en_foto.size
    ropa_generada = np.isin(partes_generada, list(ROPA[GarmentCategory.FULL]))
    alto, ancho_total = partes_generada.shape

    def marco(xs, ys):
        """Centro, eje largo, eje ancho y alargamiento (largo entre ancho) de unos píxeles."""
        puntos = np.stack([xs, ys], axis=1).astype(np.float32)
        centro = puntos.mean(axis=0)
        valores, vectores = np.linalg.eigh(np.cov((puntos - centro).T))
        return centro, vectores[:, -1], vectores[:, 0], float(np.sqrt(valores[-1] / max(float(valores[0]), 1e-6)))

    def tramo(gy, gx, fy, fx, union) -> None:
        """Un trozo recto del brazo generado (gy, gx) y el brazo de la foto que le toca (fy, fx)."""
        if len(gy) < 20 or len(fy) < 20:
            return
        centro, largo, ancho_, alargado = marco(gx, gy)
        if alargado < BRAZO_RECTO:
            # Lo que asoma del brazo generado no tiene dirección: una mano que
            # sale de una manga larga, o un brazo doblado por el codo.
            de_la_foto = marco(fx, fy)
            if de_la_foto[3] >= BRAZO_RECTO:
                centro, largo, ancho_, _ = de_la_foto  # la mano no tiene eje; el brazo de la foto, sí
            elif union is None and len(gy) > 200:
                # Doblado: cada mitad es más recta. El corte entre las dos no
                # es un dobladillo, y cada mitad lo sabe por dónde queda la otra.
                s = (np.stack([gx, gy], axis=1) - centro) @ largo
                fs = (np.stack([fx, fy], axis=1) - centro) @ largo
                medio = float(np.median(s))
                junta = centro + medio * largo
                tramo(gy[s < medio], gx[s < medio], fy[fs < medio], fx[fs < medio], junta)
                tramo(gy[s >= medio], gx[s >= medio], fy[fs >= medio], fx[fs >= medio], junta)
                return
            else:
                return  # sin eje fiable no se toca nada: se queda la regla de siempre
        puntos = np.stack([gx, gy], axis=1).astype(np.float32)
        s = (puntos - centro) @ largo
        foto = np.stack([fx, fy], axis=1).astype(np.float32) - centro
        fs, fc = foto @ largo, foto @ ancho_

        c = (puntos - centro) @ ancho_
        ancho = max(float(np.ptp(c)), 1.0)
        dentro = np.ones(len(fy), dtype=bool)
        for extremo, signo in ((float(s.min()), 1.0), (float(s.max()), -1.0)):
            if union is not None:
                otro = float(s.max()) if signo > 0 else float(s.min())
                s_union = float((union - centro) @ largo)
                if abs(s_union - extremo) < abs(s_union - otro):
                    continue  # por este lado sigue el otro trozo del mismo brazo
            mas_alla = (fs < extremo - hueco) if signo > 0 else (fs > extremo + hueco)
            if not mas_alla.any():
                continue  # el brazo de la foto acaba aquí también: no hay manga que respetar
            # El dobladillo: hasta dónde llega la piel generada, a cada ancho.
            cerca = np.abs(s - extremo) <= max(2.0 * hueco, 0.75 * ancho)
            casilla = np.round((c[cerca] - c.min()) / 2.0).astype(np.int64)
            limite = np.full(int(casilla.max()) + 1, np.inf if signo > 0 else -np.inf, dtype=np.float32)
            (np.minimum if signo > 0 else np.maximum).at(limite, casilla, s[cerca])
            con_dato = np.nonzero(np.isfinite(limite))[0]
            # Del perfil del extremo, solo lo que da a ropa es dobladillo. Con
            # el brazo en diagonal y el dobladillo horizontal, la otra mitad
            # del perfil es el costado del brazo, que da al fondo: ajustando
            # la recta a las dos mitades salía una diagonal que no era nada.
            en_c_todas = con_dato * 2.0 + float(c.min())
            fuera = centro + (limite[con_dato] - signo * 4.0)[:, None] * largo + en_c_todas[:, None] * ancho_
            fx_, fy_ = np.round(fuera[:, 0]).astype(np.int64), np.round(fuera[:, 1]).astype(np.int64)
            cabe = (fx_ >= 0) & (fx_ < ancho_total) & (fy_ >= 0) & (fy_ < alto)
            da_a_ropa = np.zeros(len(con_dato), dtype=bool)
            da_a_ropa[cabe] = ropa_generada[fy_[cabe], fx_[cabe]]
            con_dato = con_dato[da_a_ropa]
            # Sin dobladillo reconocible se corta en perpendicular, justo donde
            # acaba la piel generada. Nunca «todo lo de más allá»: con una
            # chaqueta de manga larga, de la que solo asoma la mano, eso
            # devolvía el brazo entero de la foto y borraba la manga.
            pendiente, origen = 0.0, extremo
            orilla = max(1, round(0.15 * len(con_dato)))  # las esquinas redondeadas no son dobladillo
            centrales = con_dato[orilla:-orilla] if len(con_dato) > 2 * orilla + 4 else con_dato
            if len(centrales) >= 5:
                en_c = centrales * 2.0 + float(c.min())
                pendiente = float(np.clip(np.polyfit(en_c, limite[centrales], 1)[0], -1.0, 1.0))
                origen = float(np.median(limite[centrales] - pendiente * en_c))
            recta = pendiente * fc + origen
            dentro &= (fs >= recta) if signo > 0 else (fs <= recta)
        al_aire[fy[dentro], fx[dentro]] = True

    cuantas_g, etiquetas_g, stats_g, _ = cv2.connectedComponentsWithStats(en_generada.astype(np.uint8), 8)
    _, etiquetas_f = cv2.connectedComponents(en_foto.astype(np.uint8), connectivity=8)
    for k in range(1, cuantas_g):
        if stats_g[k, cv2.CC_STAT_AREA] < minimo:
            continue
        gy, gx = np.nonzero(etiquetas_g == k)
        comun = en_foto[gy, gx]
        if comun.mean() < BRAZO_COMUN_MINIMO:
            continue  # el modelo ha puesto el brazo en otro sitio: no hay con qué comparar
        suyos = np.unique(etiquetas_f[gy[comun], gx[comun]])
        fy, fx = np.nonzero(np.isin(etiquetas_f, suyos[suyos > 0]))
        tramo(gy, gx, fy, fx, None)
    return al_aire


def _fondo_de_la_foto(
    persona: np.ndarray,
    generada: np.ndarray,
    partes_persona: np.ndarray,
    partes_generada: np.ndarray,
    vieja: np.ndarray,
    lado: int,
) -> tuple[np.ndarray, np.ndarray | None]:
    """Dónde la imagen generada enseña fondo, y el fondo de la foto que va ahí.

    Devuelve el mapa (0 a 1) y el fondo de la foto prolongado por debajo de la
    persona. Si la foto casi no tiene fondo, el mapa es cero y no hay fondo.
    """
    import cv2

    borde = max(2, round(BORDE_DEL_FONDO * lado))
    disco = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * borde + 1, 2 * borde + 1))

    # Fondo es lo de FUERA de la silueta, no todo lo que el analizador llama
    # fondo: ver `_solida`.
    fuera_en_la_foto = ~_solida((partes_persona != P.FONDO) | vieja, lado)
    fuera_en_la_generada = ~_solida(partes_generada != P.FONDO, lado)

    sombra = max(2, round(SOMBRA_DE_LA_PRENDA_VIEJA * lado))
    cerca_de_la_vieja = cv2.dilate(
        vieja.astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * sombra + 1, 2 * sombra + 1)),
    ).astype(bool)
    seguro_foto = cv2.erode(fuera_en_la_foto.astype(np.uint8), disco).astype(bool)
    seguro_foto &= ~cerca_de_la_vieja
    seguro_generado = cv2.erode(
        (fuera_en_la_foto & fuera_en_la_generada).astype(np.uint8), disco
    ).astype(bool)
    if seguro_foto.mean() < FONDO_MINIMO or seguro_generado.mean() < FONDO_MINIMO:
        return np.zeros(vieja.shape, dtype=np.float32), None

    de_la_foto = _continuar(persona, seguro_foto)
    del_modelo = _extender(generada, seguro_generado)

    al_fondo = np.linalg.norm(generada - del_modelo, axis=2)
    es_fondo = fuera_en_la_generada & (al_fondo < COLOR_DE_FONDO)

    # Y más parecido al fondo que a la piel de al lado: un hombro claro contra
    # una pared clara queda a menos de `COLOR_DE_FONDO` de la pared, y si el
    # analizador lo dejó sin etiquetar se cambiaría por pared.
    piel = cv2.erode(np.isin(partes_generada, list(PIEL)).astype(np.uint8), disco).astype(bool)
    if piel.mean() >= PIEL_MINIMA:
        es_fondo &= al_fondo < np.linalg.norm(generada - _extender(generada, piel), axis=2)

    # El último píxel de la prenda, hacia el fondo, es mitad prenda y mitad
    # fondo DEL MODELO: también se cambia, o queda un filo claro.
    canto = max(1, round(CANTO_DE_LA_PRENDA * lado))
    es_fondo = cv2.dilate(
        es_fondo.astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * canto + 1, 2 * canto + 1)),
    )
    relleno = cv2.GaussianBlur(es_fondo.astype(np.float32), (0, 0), 1.0)
    return np.clip(relleno, 0.0, 1.0), de_la_foto


def _solida(figura: np.ndarray, lado: int) -> np.ndarray:
    """La figura con sus huecos tapados: lo que queda encerrado en ella no es fondo.

    El analizador no tiene etiqueta para lo que la persona sostiene. El móvil
    de una foto frente al espejo sale como «fondo», y si se toma por fondo, el
    relleno arrastra su dorado y el negro de su cámara hacia los hombros: pasó
    con la primera prueba del vestido de noche. Se cierran los pasillos
    estrechos que unen esos huecos con el exterior —entre el pelo y el
    hombro— y lo que no toca el marco de la imagen es figura.
    """
    import cv2

    radio = max(2, round(CIERRE_DE_LA_FIGURA * lado))
    disco = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radio + 1, 2 * radio + 1))
    cerrada = cv2.morphologyEx(figura.astype(np.uint8), cv2.MORPH_CLOSE, disco)
    cuantas, etiquetas = cv2.connectedComponents(1 - cerrada, connectivity=4)
    exterior = np.zeros(cuantas, dtype=bool)
    exterior[np.concatenate([etiquetas[0], etiquetas[-1], etiquetas[:, 0], etiquetas[:, -1]])] = True
    exterior[0] = False
    return ~exterior[etiquetas]


def _continuar(imagen: np.ndarray, validos: np.ndarray) -> np.ndarray:
    """Continúa el dibujo de los píxeles `validos` por donde no los hay.

    Es el relleno de Telea (2004): avanza desde el borde hacia dentro llevando
    consigo las líneas que encuentra. Con un fondo en franjas —cielo, árboles,
    campo— las franjas siguen por detrás de la persona, que es lo que hace
    falta junto al hombro, donde asoma el hueco de la prenda vieja. Promediar
    (`_extender`) dejaba ahí una mancha pálida del color medio de las tres.
    """
    import cv2

    hueco = np.where(validos, 0, 255).astype(np.uint8)
    base = np.clip(imagen + 0.5, 0, 255).astype(np.uint8)
    relleno = cv2.inpaint(base, hueco, RADIO_DEL_RELLENO, cv2.INPAINT_TELEA).astype(np.float32)
    # Lo conocido se queda exactamente como estaba, sin pasar por 8 bits.
    return np.where(validos[..., None], imagen, relleno)


def _extender(imagen: np.ndarray, validos: np.ndarray) -> np.ndarray:
    """Prolonga el color de los píxeles `validos` hacia donde no los hay.

    Los válidos se quedan como están. Los demás toman el color de los válidos
    más cercanos, más suave cuanto más lejos quedan: se promedia en una
    pirámide de resoluciones (cada nivel solo con los válidos que contiene) y
    se baja de la más gruesa a la más fina, rellenando en cada una lo que la
    anterior no pudo. Es «push-pull» (Gortler et al., 1996).
    """
    import cv2

    peso = validos.astype(np.float32)
    niveles = [(imagen.astype(np.float32) * peso[..., None], peso)]
    while min(niveles[-1][1].shape) > 2:
        color, peso = niveles[-1]
        tamano = ((peso.shape[1] + 1) // 2, (peso.shape[0] + 1) // 2)
        niveles.append(
            (
                cv2.resize(color, tamano, interpolation=cv2.INTER_AREA),
                cv2.resize(peso, tamano, interpolation=cv2.INTER_AREA),
            )
        )

    color, peso = niveles[-1]
    media = color.reshape(-1, 3).sum(axis=0) / max(float(peso.sum()), 1e-6)
    relleno = np.broadcast_to(media.astype(np.float32), color.shape).copy()
    for color, peso in reversed(niveles):
        subido = cv2.resize(
            relleno, (peso.shape[1], peso.shape[0]), interpolation=cv2.INTER_LINEAR
        ).reshape(color.shape)
        propio = color / np.maximum(peso, 1e-6)[..., None]
        # Con una cuarta parte de la celda conocida, ya manda lo propio.
        confianza = np.clip(peso * 4.0, 0.0, 1.0)[..., None]
        relleno = propio * confianza + subido * (1.0 - confianza)
    return relleno


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
