"""Bloqueo estructural: la IA puede mejorar el aspecto, no cambiar la prenda.

EL PROBLEMA, CON SUS MEDIDAS
----------------------------
La edición generativa de OpenAI no garantiza la geometría, y la documentación lo
dice: *«masking with GPT Image is entirely prompt-based»*. Medido seis veces
con los dos modelos, fidelidad alta, máscara binaria, tamaño nativo, la tela
como imagen de referencia y partiendo del render correcto: devuelve una prenda
parecida. Manga larga donde no había, un cuello cerrado donde había escote, la
espalda de la camiseta en vez del frente.

Los sistemas que sí conservan la forma (ZeST, IDM-VTON, CatVTON) lo consiguen
con condicionamiento estructural duro dentro del propio modelo —profundidad por
ControlNet, codificadores de la prenda—, que la API de OpenAI no ofrece. Así
que aquí la forma no se le PIDE al modelo: se le IMPIDE cambiarla, después.

LA IDEA: BANDAS DE FRECUENCIA
-----------------------------
Una imagen se puede separar por escalas:

- **Forma** (lo ancho): pliegues, volumen, dónde da la luz.
- **Estructura** (lo medio): costuras, cantos, cortes, cuellos, botones.
- **Textura** (lo más fino): el grano del hilo, el chispeo del brillo.

La prenda del usuario ES su forma y su estructura. Esas dos bandas salen
SIEMPRE del render determinista, que las conserva por construcción. De la IA
se toma solo la textura, y solo donde la estructura de la IA COINCIDE con la
de la prenda, medido con una correlación local. Donde la IA inventó un corte o
movió un pliegue, la coincidencia cae y esa zona se queda con el render.

Dos cosas más:

- El **color** sale del render, que es el de la ficha de la tela. La IA no
  puede cambiar un burdeos por otro burdeos.
- Del render de la IA se toma también su **carácter tonal** —cuánto contraste
  y cuánto brillo tiene una tela fotografiada— con una curva de tono MONÓTONA.
  Una curva monótona no cambia el orden de los brillos, así que no puede mover
  una forma de sitio: solo hace que la misma forma se vea más o menos
  fotográfica.

LA GARANTÍA
-----------
El resultado difiere del render determinista solo en la banda más fina, y solo
donde la IA coincide con la prenda, más una curva de tono monótona. Una prenda
distinta, volteada o recortada no puede salir por aquí: en el peor caso, sale
el render exacto.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from app.textil.filtros import desenfocar, media_de_caja

LUMINANCIA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)

#: Escala que separa FORMA de ESTRUCTURA, como divisor del ancho de la prenda.
ESCALA_DE_LA_FORMA = 60.0

#: Escala que separa ESTRUCTURA de TEXTURA, en píxeles. Pequeña a propósito:
#: una costura de dos píxeles tiene que caer en la estructura, que es del
#: render. A la IA solo se le deja lo que no puede formar una línea.
ESCALA_DE_LA_TEXTURA = 1.0

#: Ventana de la correlación que decide si la IA coincide con la prenda, como
#: divisor del ancho de la prenda.
VENTANA_DE_COINCIDENCIA = 40.0

#: Correlación a partir de la cual la estructura de la IA coincide con la de la
#: prenda, y a partir de la cual se fía del todo.
COINCIDENCIA_MINIMA = 0.35
COINCIDENCIA_PLENA = 0.75

#: Si en una zona la IA tiene mucha más estructura que el render —un botón, un
#: bolsillo, un corte que no existe—, la textura de esa zona no se toma aunque
#: la correlación salga alta por casualidad.
EXCESO_DE_ESTRUCTURA = 4.0

#: Cuánto se acerca el tono del render al de la IA: 0, nada; 1, del todo. A
#: medias, porque la exposición del modelo no siempre es buena.
FUERZA_DEL_TONO = 0.5

#: Fracción de la prenda en la que la IA tiene que coincidir para que se use
#: algo de ella, y a partir de la cual se fía del todo de su tono.
#:
#: Medido con cuatro salidas de IA que eran OTRA prenda (la espalda de la
#: camiseta, otra camiseta, un vestido de punto sin abertura, un vestido de
#: cuello cerrado): coincidían en 0,3–1,0%. Esas coincidencias sueltas son
#: azar, y aplicar su tono metía un moteado en la abertura del vestido.
ACUERDO_MINIMO = 0.15
ACUERDO_PLENO = 0.50


@dataclass(frozen=True)
class Bloqueado:
    imagen: Image.Image
    #: Fracción de la prenda en la que se usó la textura de la IA. Cero quiere
    #: decir que la IA cambió la prenda en todas partes y se descartó entera.
    aportado: float


def bloquear_estructura(
    render: Image.Image, generada: Image.Image, mascara: Image.Image
) -> Bloqueado:
    """Funde `generada` en `render` sin dejar que cambie la prenda.

    `render` es el retexturizado determinista, que conserva la prenda exacta.
    `generada` es la salida del modelo, del mismo tamaño.
    """
    render = render.convert("RGB")
    generada = generada.convert("RGB").resize(render.size, Image.Resampling.LANCZOS)
    if mascara.size != render.size:
        mascara = mascara.resize(render.size, Image.Resampling.BILINEAR)

    alfa = np.asarray(mascara.convert("L"), dtype=np.float32) / 255.0
    dentro = alfa > 0.5
    if dentro.sum() < 64:
        return Bloqueado(imagen=render, aportado=0.0)

    lineal_r = _a_lineal(np.asarray(render, dtype=np.float32) / 255.0)
    lineal_g = _a_lineal(np.asarray(generada, dtype=np.float32) / 255.0)
    ell_r = np.log(np.maximum(lineal_r @ LUMINANCIA, 1e-4))
    ell_g = np.log(np.maximum(lineal_g @ LUMINANCIA, 1e-4))

    columnas = np.nonzero(dentro.any(axis=0))[0]
    ancho = float(columnas[-1] - columnas[0] + 1)

    forma_r = desenfocar(ell_r, max(2.0, ancho / ESCALA_DE_LA_FORMA))
    liso_r = desenfocar(ell_r, ESCALA_DE_LA_TEXTURA)
    estructura_r = liso_r - forma_r
    textura_r = ell_r - liso_r

    forma_g = desenfocar(ell_g, max(2.0, ancho / ESCALA_DE_LA_FORMA))
    liso_g = desenfocar(ell_g, ESCALA_DE_LA_TEXTURA)
    estructura_g = liso_g - forma_g
    textura_g = ell_g - liso_g

    puerta = _coincidencia(estructura_r, estructura_g, dentro, ancho)
    acuerdo = float(puerta[dentro].mean())

    # VETO GLOBAL. Si la IA coincide con la prenda en muy poca superficie, lo que
    # ha devuelto es OTRA prenda —la espalda de la camiseta, un vestido de otro
    # corte— y las pocas zonas que casan son casualidad. Se descarta entera,
    # tono incluido: su distribución de brillos sale de otros pliegues.
    if acuerdo < ACUERDO_MINIMO:
        return Bloqueado(imagen=render, aportado=0.0)

    # Forma y estructura del render, con el carácter tonal de la IA encima, en
    # proporción a cuánto se fía de ella.
    fuerza = FUERZA_DEL_TONO * min(1.0, acuerdo / ACUERDO_PLENO)
    base = _curva_de_tono(liso_r, liso_g, dentro, fuerza)
    ell = base + puerta * textura_g + (1.0 - puerta) * textura_r

    # Se escala el RGB del render por el cambio de luminancia: el color —el
    # cociente entre canales— es exactamente el del render, el de la ficha.
    factor = np.exp(np.clip(ell - ell_r, -1.5, 1.5))[..., None]
    fundido = _a_srgb(lineal_r * factor)

    original = np.asarray(render, dtype=np.float32) / 255.0
    salida = fundido * alfa[..., None] + original * (1.0 - alfa[..., None])
    imagen = Image.fromarray(np.clip(salida * 255.0 + 0.5, 0, 255).astype(np.uint8), mode="RGB")
    return Bloqueado(imagen=imagen, aportado=float(puerta[dentro].mean()))


def _coincidencia(
    estructura_r: np.ndarray, estructura_g: np.ndarray, dentro: np.ndarray, ancho: float
) -> np.ndarray:
    """Dónde la estructura de la IA es la de la prenda: de 0 a 1.

    Correlación normalizada en una ventana: vale 1 donde las dos bandas suben y
    bajan juntas —la misma costura en el mismo sitio— y 0 o menos donde no.
    Una camiseta vuelta de espaldas da correlación baja en todas partes.
    """
    radio = max(3, round(ancho / VENTANA_DE_COINCIDENCIA))
    media_r = media_de_caja(estructura_r, radio)
    media_g = media_de_caja(estructura_g, radio)
    var_r = np.maximum(media_de_caja(estructura_r**2, radio) - media_r**2, 0.0)
    var_g = np.maximum(media_de_caja(estructura_g**2, radio) - media_g**2, 0.0)
    cov = media_de_caja(estructura_r * estructura_g, radio) - media_r * media_g
    correlacion = cov / np.sqrt(var_r * var_g + 1e-8)

    puerta = np.clip(
        (correlacion - COINCIDENCIA_MINIMA) / (COINCIDENCIA_PLENA - COINCIDENCIA_MINIMA), 0.0, 1.0
    )
    # Estructura que el render no tiene: invento, aunque correlacione.
    puerta[var_g > EXCESO_DE_ESTRUCTURA * var_r + 1e-5] = 0.0
    puerta[~dentro] = 0.0
    # Sin escalones: la frontera entre lo aceptado y lo descartado no debe verse.
    return np.clip(desenfocar(puerta, radio / 2.0), 0.0, 1.0)


def _curva_de_tono(
    origen: np.ndarray, referencia: np.ndarray, dentro: np.ndarray, fuerza: float
) -> np.ndarray:
    """Lleva la distribución de brillos de `origen` hacia la de `referencia`.

    Igualación de histogramas por cuantiles, dentro de la prenda, con las
    medianas alineadas para que el tono medio —el color de la tela— no se
    mueva. La curva es monótona: el píxel más claro sigue siendo el más claro,
    así que ninguna forma cambia de sitio.
    """
    cuantiles = np.linspace(0.5, 99.5, 100)
    de = np.percentile(origen[dentro], cuantiles)
    a = np.percentile(referencia[dentro], cuantiles)
    a = a - np.median(referencia[dentro]) + np.median(origen[dentro])
    a = np.maximum.accumulate(a)  # monótona aunque el ruido diga otra cosa
    curva = np.interp(origen, de, a)
    return origen + fuerza * (curva - origen)


def _a_lineal(c: np.ndarray) -> np.ndarray:
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _a_srgb(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)
