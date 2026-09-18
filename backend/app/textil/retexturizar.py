"""Estampar una tela sobre una prenda conservando sus pliegues reales.

LA IDEA, EN UNA FRASE
---------------------
La fotografía de una prenda ya contiene, gratis, toda la información difícil:
dónde hay un pliegue, dónde da la luz, dónde cae una sombra. Esa información no
depende del color de la prenda —depende de su forma—, así que se puede separar
del color y reutilizarla con otra tela.

POR QUÉ NO BASTA MULTIPLICAR POR EL BRILLO
------------------------------------------
Es el primer intento de todo el mundo y está mal. Si la prenda original es azul
marino, su brillo es bajo en toda la superficie, y multiplicar deja la tela
nueva oscura aunque sea blanca. Si es blanca, el brillo es casi 1 y la tela
sale plana, sin un solo pliegue.

El brillo mezcla dos cosas: **cuánta luz refleja el material** (su color propio)
y **cuánta luz le llega** (la forma). Lo que queremos es lo segundo.

Se separan dividiendo: se mide el brillo típico de la prenda —su color propio—
y se divide el brillo de cada píxel entre él. Lo que queda vale 1 donde la luz
es normal, menos en un pliegue y más en un brillo, **y ya no depende del color
original**. Esa razón es la que se traslada a la tela nueva.

EN LUZ LINEAL, NO EN sRGB
-------------------------
Los valores de un PNG no son proporcionales a la luz: llevan una curva encima
para aprovechar los 256 niveles donde el ojo distingue mejor. Multiplicar sobre
esos números no multiplica luz, y las sombras salen más oscuras de lo que
deberían.

Es el detalle que separa un resultado que «casi cuela» de uno que parece una
fotografía, y cuesta dos funciones. Se deshace la curva, se multiplica, y se
vuelve a poner.

LO QUE ESTE MOTOR NO PUEDE HACER
--------------------------------
No cambia cómo CAE la tela. Si la foto es de un vestido de seda fluida y le
pones una lona rígida, la lona caerá como seda, porque los pliegues son los de
la foto. Para eso haría falta simular el tejido, que es otro problema y mucho
mayor.

Y sobre un boceto no hace nada útil: un dibujo de líneas no tiene sombras, así
que la razón vale 1 en todas partes y la tela sale plana. Eso no es un fallo,
es la razón por la que los bocetos van al motor generativo.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from app.textil.filtros import desenfocar as _desenfocar, reescalar

#: Hasta dónde se deja llegar la sombra y el brillo.
#:
#: Un pliegue muy cerrado o un reflejo quemado dan razones extremas que, sobre
#: la tela nueva, se ven como manchas negras o blancas. Recortarlas conserva el
#: relieve y quita los artefactos.
SOMBRA_MINIMA = 0.30
LUZ_MAXIMA = 1.85

#: Cuánto detalle fino se conserva de la prenda original, de 0 a 1.
#:
#: El mapa de luz se desenfoca para borrar el TEJIDO de la prenda original
#: —sus hilos, su trama—, que es justo lo que venimos a sustituir. Pero ese
#: mismo desenfoque se lleva por delante las costuras, los botones y los
#: pespuntes, que sí queremos conservar porque son la prenda y no la tela.
#:
#: Devolviendo una fracción del detalle se recuperan sin que vuelva la trama
#: vieja. 0,35 es donde las costuras se ven y el tejido antiguo no.
DETALLE_CONSERVADO = 0.35

#: Cuánto se dobla el estampado con el relieve, en fracciones del mosaico.
#:
#: Es el único número de este módulo que hay que ajustar mirando, porque la
#: relación entre sombra y pendiente depende de dónde estuviera la luz al hacer
#: la foto, y eso no se sabe.
#:
#: Medido con un cuadro vichy sobre camisa y jersey: a 0,06 se nota que la tela
#: envuelve el hombro; a 0,12 todavía es creíble; a 0,20 aparecen remolinos en
#: el cuello y el dibujo empieza a parecer líquido; a 0,35 se derrite. Con 0 el
#: cuadro sale perfectamente recto sobre una manga curva, que es lo que delata
#: el montaje.
DOBLADO_DEL_ESTAMPADO = 0.10

#: Brillo de referencia mínimo. Una prenda negra sobre fondo negro tiene un
#: brillo medio cercano a cero, y dividir por él manda la razón al infinito.
BRILLO_MINIMO = 0.012


@dataclass(frozen=True)
class Retexturizado:
    imagen: Image.Image
    #: Cuánto relieve tenía la prenda original (desviación de la razón de luz).
    #:
    #: Por debajo de ~0,04 la prenda no tenía sombras que reutilizar —un boceto,
    #: o una foto plana— y el resultado sale como un recorte de papel pintado.
    #: Se expone para poder avisar en vez de entregar algo soso sin explicación.
    contraste: float


def retexturizar(
    prenda: Image.Image,
    mascara: Image.Image,
    tela: Image.Image,
    *,
    repeticiones: int = 6,
    caja: tuple[int, int, int, int] | None = None,
) -> Retexturizado:
    """Devuelve la prenda vestida con la tela.

    `repeticiones` es cuántas veces se repite el mosaico a lo ancho de la
    prenda. Es la escala del estampado: en un liso da igual, en un cuadro
    escocés lo es todo.
    """
    prenda = prenda.convert("RGB")
    if mascara.size != prenda.size:
        mascara = mascara.resize(prenda.size, Image.Resampling.BILINEAR)

    alfa = np.asarray(mascara.convert("L"), dtype=np.float32)[..., None] / 255.0
    original = np.asarray(prenda, dtype=np.float32) / 255.0

    dentro = alfa[..., 0] > 0.5
    if not dentro.any():
        # Sin máscara no hay dónde poner la tela. Devolver la prenda tal cual
        # es más honesto que pintarla entera.
        return Retexturizado(imagen=prenda, contraste=0.0)

    lineal = _a_luz_lineal(original)
    brillo = lineal @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)

    # El color propio de la prenda: la mediana del brillo dentro de ella. Se
    # usa la mediana y no la media porque un fondo que se haya colado en la
    # máscara, o un brillo especular, arrastran la media y no la mediana.
    referencia = max(float(np.median(brillo[dentro])), BRILLO_MINIMO)

    razon = np.clip(brillo / referencia, SOMBRA_MINIMA, LUZ_MAXIMA)
    contraste = float(razon[dentro].std())

    pendiente = _pendiente_de_la_prenda(razon)
    razon = _separar_forma_de_trama(razon, prenda.size)
    campo = _tender_la_tela(tela, prenda.size, repeticiones, caja, pendiente)

    vestida = _a_srgb(_a_luz_lineal(campo) * razon[..., None])
    compuesta = vestida * alfa + original * (1.0 - alfa)

    imagen = Image.fromarray(np.clip(compuesta * 255.0, 0, 255).astype(np.uint8), mode="RGB")
    return Retexturizado(imagen=imagen, contraste=contraste)


#: Cuánto más oscuro queda el borde de un boceto respecto a su centro.
#: Es el volumen que se le inventa, y es poco a propósito: un boceto no tiene
#: información de forma, así que pasarse sería mentir con más énfasis.
VOLUMEN_DEL_BOCETO = 0.38

#: Un píxel más oscuro que esto respecto a la media de la prenda es trazo.
UMBRAL_DE_TRAZO = 0.62


def vestir_boceto(
    boceto: Image.Image,
    mascara: Image.Image,
    tela: Image.Image,
    *,
    repeticiones: int = 6,
    caja: tuple[int, int, int, int] | None = None,
) -> Retexturizado:
    """Rellena un boceto con una tela, conservando el trazo del dibujo.

    POR QUÉ EXISTE ESTO Y NO SE MANDA TODO A LA IA
    ----------------------------------------------
    Se probó la IA con un boceto real —camisa con cartera de botones, bolsillo
    de pecho y cuello camisero— y devolvió una túnica lisa de cuello barco. Con
    el modelo mini y con el completo, y con `input_fidelity="high"`, que es el
    parámetro que existe justo para evitarlo. El modelo no conserva el diseño:
    lo reinterpreta.

    Para un producto cuya promesa es «mira TU diseño con otra tela», eso es
    exactamente el resultado equivocado. Una modista que dibuja cinco botones
    quiere ver cinco botones.

    Así que aquí el dibujo manda. La tela rellena el interior, el trazo se
    conserva por encima intacto, y el volumen se insinúa oscureciendo los
    bordes. No es una fotografía —no lo aparenta— pero es SU prenda.

    El camino generativo sigue estando, y para lo que sí sabe hacer: convertir
    el boceto en algo fotorrealista. Pero se pide a conciencia, sabiendo que
    reinterpreta y que se cobra.

    DE DÓNDE SALE EL VOLUMEN
    ------------------------
    De la distancia al borde de la silueta. Una prenda es un cuerpo blando: el
    centro está de frente a la luz y los bordes se curvan y se alejan. Un
    desenfoque ancho de la máscara da justo eso —1 en el centro, medio en el
    canto— y es un modelado pobre pero honesto, porque no pretende haber
    deducido una forma que en el dibujo no está.
    """
    boceto = boceto.convert("RGB")
    if mascara.size != boceto.size:
        mascara = mascara.resize(boceto.size, Image.Resampling.BILINEAR)

    alfa = np.asarray(mascara.convert("L"), dtype=np.float32) / 255.0
    original = np.asarray(boceto, dtype=np.float32) / 255.0

    dentro = alfa > 0.5
    if not dentro.any():
        return Retexturizado(imagen=boceto, contraste=0.0)

    # Volumen inventado: lejos del borde, más luz.
    hinchado = _desenfocar(alfa, max(8.0, boceto.width / 26.0))
    volumen = 1.0 - VOLUMEN_DEL_BOCETO * (1.0 - np.clip(hinchado, 0.0, 1.0))

    campo = _tender_la_tela(tela, boceto.size, repeticiones, caja)
    vestida = _a_srgb(_a_luz_lineal(campo) * volumen[..., None])

    # EL TRAZO SE CONSERVA, Y ES LO QUE HACE QUE SIGA SIENDO SU DISEÑO.
    #
    # Se detecta por oscuridad relativa: el papel es claro y la tinta no. Se
    # usa el mínimo de los tres canales para que un trazo de color —azul de
    # bolígrafo, lápiz de color— cuente igual que uno negro.
    tinta = 1.0 - np.clip(original.min(axis=2) / UMBRAL_DE_TRAZO, 0.0, 1.0)
    tinta = tinta * alfa

    resultado = vestida * (1.0 - tinta[..., None]) + original * tinta[..., None]
    compuesta = resultado * alfa[..., None] + original * (1.0 - alfa[..., None])

    imagen = Image.fromarray(np.clip(compuesta * 255.0, 0, 255).astype(np.uint8), mode="RGB")
    return Retexturizado(imagen=imagen, contraste=float(volumen[dentro].std()))


def _separar_forma_de_trama(razon: np.ndarray, tamano: tuple[int, int]) -> np.ndarray:
    """Quita el tejido viejo del mapa de luz y deja los pliegues y las costuras.

    Los pliegues son formas grandes y suaves; la trama de un tejido es ruido
    fino. Un desenfoque separa lo uno de lo otro: lo que sobrevive es la forma.
    Después se devuelve una parte de lo fino, que es donde viven las costuras.
    """
    suave = _desenfocar(razon, max(1.0, tamano[0] / 220.0))
    return suave + DETALLE_CONSERVADO * (razon - suave)


#: Lado al que se reduce la imagen para calcular el modelado.
LADO_DEL_MODELADO = 256


def _pendiente_de_la_prenda(razon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Hacia dónde se inclina la superficie, en cada punto.

    Devuelve el gradiente del modelado: dos campos que dicen cuánto y hacia
    dónde se curva la prenda. Es lo que dobla el estampado.

    SE DERIVA EN PEQUEÑO, Y ESE ORDEN ES TODO
    -----------------------------------------
    El primer intento reducía la imagen, desenfocaba, la AMPLIABA de vuelta y
    derivaba el resultado. Salía destrozado: la ampliación pasaba por enteros
    de 8 bits y dejaba escalones de 1/120, invisibles a la vista pero enormes
    para una derivada. El estampado se rompía en tiras verticales.

    Derivando ANTES de ampliar, se deriva un campo que sí es suave, y lo que se
    amplía es ya el resultado. Un gradiente de un campo de frecuencia muy baja
    también es de frecuencia muy baja, así que ampliarlo no inventa nada.

    Y de paso sale gratis: el desenfoque ancho, que es la parte cara, se hace
    sobre una imagen dieciséis veces más pequeña.
    """
    alto, ancho = razon.shape
    escala = min(1.0, LADO_DEL_MODELADO / max(ancho, alto))

    pequeno = reescalar(razon, max(8, round(ancho * escala)), max(8, round(alto * escala)))
    suave = _desenfocar(pequeno, max(4.0, pequeno.shape[1] / 22.0))

    gy, gx = np.gradient(suave)

    # Normalizado por su propia dispersión, para que el efecto sea el mismo en
    # una foto de estudio muy contrastada y en una plana, en vez de depender de
    # lo dura que fuera la luz. Se hace aquí, sobre el campo pequeño, donde la
    # dispersión es la de la forma y no la del ruido.
    gy = np.clip(gy / (float(gy.std()) or 1.0), -3.0, 3.0)
    gx = np.clip(gx / (float(gx.std()) or 1.0), -3.0, 3.0)

    return reescalar(gx, ancho, alto), reescalar(gy, ancho, alto)


def _tender_la_tela(
    tela: Image.Image,
    tamano: tuple[int, int],
    repeticiones: int,
    caja: tuple[int, int, int, int] | None,
    pendiente: tuple[np.ndarray, np.ndarray] | None = None,
) -> np.ndarray:
    """Repite el mosaico de tela hasta cubrir la imagen, doblándolo con la prenda.

    LA ESCALA SE MIDE SOBRE LA PRENDA, NO SOBRE LA IMAGEN
    -----------------------------------------------------
    Si se usara el ancho de la imagen, la misma tela cambiaría de tamaño según
    el margen que tuviera la foto alrededor, y dos pruebas de la misma prenda
    dejarían de ser comparables — que es justo lo que el producto promete.

    SE REPITE SIN ESPEJAR
    ---------------------
    Espejando no se notarían las uniones del mosaico, pero una raya se
    convertiría en un galón en cada una. En confección la dirección del hilo es
    un dato real, no un detalle estético.

    EL ESTAMPADO SE DOBLA CON LOS PLIEGUES
    --------------------------------------
    Repetir el dibujo en plano delata el montaje en cuanto la tela tiene
    estampado: los cuadros salen perfectamente rectos sobre una manga arrugada,
    como papel pintado sobre una escultura.

    La pista de por dónde se dobla ya la tenemos, y gratis: el mapa de luz. Su
    gradiente apunta hacia donde la superficie se inclina, así que desplazando
    las coordenadas de la textura en esa dirección —y en proporción a la
    pendiente— el dibujo se curva siguiendo el relieve.

    No es una reconstrucción de la forma en 3D: deducir el volumen exacto a
    partir de sombras es un problema sin solución única. Es una aproximación
    que acierta en lo que se ve, y cuesta un gradiente.
    """
    ancho_prenda = (caja[2] - caja[0]) if caja else tamano[0]
    ancho_prenda = max(ancho_prenda, 8)

    lado = max(8, round(ancho_prenda / max(1, repeticiones)))
    mosaico = np.asarray(
        tela.convert("RGB").resize((lado, lado), Image.Resampling.LANCZOS), dtype=np.float32
    ) / 255.0

    columnas = np.arange(tamano[0], dtype=np.float32)[None, :]
    filas = np.arange(tamano[1], dtype=np.float32)[:, None]
    x = np.broadcast_to(columnas, (tamano[1], tamano[0])).copy()
    y = np.broadcast_to(filas, (tamano[1], tamano[0])).copy()

    if pendiente is not None:
        gx, gy = pendiente
        empuje = lado * DOBLADO_DEL_ESTAMPADO
        x += gx * empuje
        y += gy * empuje

    # Muestreo con envoltura: el mosaico es periódico, así que el módulo lo
    # repite sin tener que construir la imagen entera repetida en memoria.
    ix = np.mod(x.astype(np.int32), lado)
    iy = np.mod(y.astype(np.int32), lado)
    return mosaico[iy, ix]


# --- Conversión de color ----------------------------------------------------
#
# Las dos mitades de la curva sRGB. El tramo recto cerca del negro no es un
# capricho de la norma: evita que la derivada se dispare en cero, que es lo que
# haría una potencia pura.


def _a_luz_lineal(c: np.ndarray) -> np.ndarray:
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _a_srgb(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)
