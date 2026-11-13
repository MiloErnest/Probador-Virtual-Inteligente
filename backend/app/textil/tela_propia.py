"""La tela del propio taller: de UNA foto de móvil al mosaico que se estampa.

QUÉ AÑADE A `digitalizar.py`
----------------------------
`digitalizar.py` ya sabe sacar el mosaico de una tela lisa, de una raya o de un
estampado: con él salieron las telas reales de la tienda. Pero allí cada recorte
lo eligió alguien a mano, mirando la foto de la estantería. Aquí la foto llega
de un usuario, sin nadie que la mire antes, y hacen falta tres cosas más:

1. **Elegir qué parte de la foto es tela.** Se pide que la tela llene el
   encuadre y se toma el centro (`MARGEN`): los bordes de una foto de móvil son
   donde aparecen la mesa, la mano o el orillo.
2. **Saber si la foto sirve** (`revisar_foto`) y decirlo con lo que hay que
   hacer, en vez de devolver un mosaico malo sin explicación.
3. **Medir la junta** del mosaico que sale, para no afirmar que se repite bien
   sin haberlo comprobado.

Nada de esto llama a un modelo generativo: no cuesta dinero, y el mosaico es la
tela de la foto, no una tela imaginada.

LOS UMBRALES ESTÁN MEDIDOS
--------------------------
Medidos el 12/11/2026 sobre las fotos reales de `scripts/muestras/` (una
estantería de lisos, una de rayas y estampados, y un floral de acuarela), sin
tocar y con desenfoque y degradados de luz añadidos a propósito:

=====================  =========  ==========  ==========  =========
Borrosidad             nítida     σ = 1       σ = 2       σ = 3
=====================  =========  ==========  ==========  =========
floral                 0,18       0,33        0,66        0,76
estantería estampados  0,26       0,42        0,67        0,80
=====================  =========  ==========  ==========  =========

=====================  =========  ==========  ==========  =========
Luz desigual           tal cual   ×1,3        ×1,6        ×2,0
=====================  =========  ==========  ==========  =========
floral                 1,07       1,23        1,41        1,63
=====================  =========  ==========  ==========  =========

(×1,6 = un lado de la foto recibe 1,6 veces la luz del otro.)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from app.textil import digitalizar as dig
from app.textil.errores import ErrorDeMotor
from app.textil.filtros import desenfocar
from app.textil.tejido_ia import LADO, medir_junta

#: Los tres caminos que sabe hacer `digitalizar.py`, con el nombre que usa la
#: API para el dibujo de la tela. Un cuadro o una tela con relieve se tratan
#: como estampado: `hacer_repetible` ya reconoce el período de un cuadro.
TIPOS = ("solid", "stripes", "print")

#: Fracción de cada lado que se descarta antes de medir. Un 10% por lado deja el
#: 80% central: lo bastante para un estampado y lejos de lo que asoma por los
#: bordes de una foto hecha a pulso.
MARGEN = 0.10

#: Lado corto, en píxeles, por debajo del cual se avisa. El recorte central se
#: lleva a `LADO` (1024 px); con 600 px de foto, el 80% central son 480 y se
#: amplía más del doble, y el estampado sale blando.
LADO_MINIMO = 600

#: Por debajo de esto no se intenta: no hay tela suficiente ni para medir un
#: color sin que mande el ruido del sensor.
LADO_IMPOSIBLE = 120

#: Borrosidad a partir de la que se avisa. Las fotos nítidas dan 0,18–0,26;
#: con un desenfoque gaussiano de σ = 2 px ya dan 0,66. A 0,5 se queda en medio,
#: más cerca de lo nítido: σ = 1 (0,33–0,42) todavía se ve bien en una prenda.
BORROSIDAD_MAXIMA = 0.5

#: Cociente entre la zona más iluminada y la más oscura de la luz de fondo a
#: partir del que se avisa. La foto real del floral da 1,07; un lado con 1,6
#: veces la luz del otro da 1,41. 1,35 avisa de eso y deja pasar una foto de
#: luz de ventana normal.
LUZ_DESIGUAL = 1.35

#: Junta máxima aceptada, en la escala de `medir_junta`. Es el mismo tope que
#: usan las pruebas del motor. Medido: un liso y una raya sintéticos, perfectos
#: por construcción, dan 2,0 (la métrica compara con el paso de un período antes,
#: y en la trama de tafetán ese paso va en contrafase); el floral cerrado da
#: 0,89, y el mismo floral SIN cerrar, 4,98.
JUNTA_MAXIMA = 3.0


@dataclass
class TelaDigitalizada:
    """Lo que sale de la foto: el mosaico y lo que se sabe de él."""

    mosaico: Image.Image
    #: Color medio del mosaico, en #rrggbb, para la ficha.
    color_hex: str
    #: `medir_junta` del mosaico: por debajo de `JUNTA_MAXIMA` no se ve.
    junta: float
    #: Avisos sobre la foto, en frases que dicen qué hacer.
    avisos: list[str] = field(default_factory=list)

    @property
    def junta_visible(self) -> bool:
        return self.junta >= JUNTA_MAXIMA


def digitalizar(foto: Image.Image, tipo: str) -> TelaDigitalizada:
    """Convierte la foto de una tela en su mosaico repetible.

    Lanza `ErrorDeMotor` si la foto no da para sacar nada; si da, pero no es
    buena, devuelve el mosaico con sus avisos: el usuario lo ve y decide.
    """
    if tipo not in TIPOS:
        raise ErrorDeMotor(
            f"No sé digitalizar una tela de tipo «{tipo}». Elige lisa, de rayas o estampada."
        )

    foto = foto.convert("RGB")
    if min(foto.size) < LADO_IMPOSIBLE:
        raise ErrorDeMotor(
            f"La foto es demasiado pequeña ({foto.size[0]}×{foto.size[1]} px) para "
            "sacar la tela. Haz otra más cerca, con la tela llenando el encuadre."
        )

    avisos = revisar_foto(foto, tipo)
    recorte = centro(foto)

    if tipo == "solid":
        mosaico = dig.muestra_lisa(dig.color_propio(recorte))
    elif tipo == "stripes":
        mosaico = _raya(recorte)
    else:
        mosaico = dig.muestra_estampada(recorte)

    junta = float(medir_junta(mosaico))
    if junta >= JUNTA_MAXIMA:
        avisos.append(
            "El mosaico deja una costura visible al repetirse. Prueba con otra foto: "
            "de frente, enfocada y con la tela llenando el encuadre."
        )

    media = np.asarray(mosaico, dtype=np.float32).reshape(-1, 3).mean(axis=0)
    color_hex = "#" + "".join(f"{int(round(c)):02x}" for c in media)

    return TelaDigitalizada(mosaico=mosaico, color_hex=color_hex, junta=junta, avisos=avisos)


def revisar_foto(foto: Image.Image, tipo: str) -> list[str]:
    """Lo que tiene mal la foto, dicho con lo que hay que hacer para arreglarlo.

    La nitidez NO se mira en una tela lisa: de ella solo se toma el color, que
    no cambia por estar desenfocada, y una lisa bien enfocada tampoco tiene
    detalle con el que distinguirla de una borrosa.
    """
    avisos: list[str] = []
    ancho, alto = foto.size

    if min(ancho, alto) < LADO_MINIMO:
        avisos.append(
            f"La foto es pequeña ({ancho}×{alto} px): el mosaico se amplía más del "
            f"doble y saldrá blando. Usa una de al menos {LADO_MINIMO} px de lado corto."
        )

    gris = _gris(centro(foto))

    if tipo != "solid" and borrosidad(gris) > BORROSIDAD_MAXIMA:
        avisos.append(
            "La foto está desenfocada o movida. Apoya los codos, toca la pantalla "
            "sobre la tela para enfocar y vuelve a hacerla."
        )

    if luz_desigual(gris) > LUZ_DESIGUAL:
        avisos.append(
            "La luz es muy desigual de un lado a otro. Ponte de frente a una "
            "ventana, sin sol directo, y que no caiga tu sombra sobre la tela."
        )

    return avisos


def centro(foto: Image.Image) -> Image.Image:
    """El 80% central de la foto: donde está la tela y no lo que asoma."""
    ancho, alto = foto.size
    dx, dy = round(ancho * MARGEN), round(alto * MARGEN)
    return foto.crop((dx, dy, ancho - dx, alto - dy))


def borrosidad(gris: np.ndarray) -> float:
    """Cuánto le falta de detalle fino a la imagen, de 0 (nítida) a 1.

    Es la medida sin referencia de Crete et al. (2007, «The blur effect»): se
    vuelve a desenfocar la imagen y se mira cuánto cambia. Una foto nítida
    pierde mucho detalle al desenfocarla; una ya borrosa, casi nada. Al comparar
    la imagen consigo misma no depende de cuánto dibujo tenga la tela, que es
    lo que hace inservible el clásico «varianza del laplaciano» con un umbral
    fijo: un estampado grande y suave daría «borroso» estando enfocado.

    Una dirección sin ningún cambio de brillo —a lo largo de una raya— no dice
    nada de la nitidez y no cuenta. Con la versión que la contaba como
    «borrosa», una raya perfecta salía desenfocada.
    """
    nucleo = np.ones(9, dtype=np.float32) / 9.0
    medidas: list[float] = []
    for eje in (0, 1):
        salto = np.abs(np.diff(gris, axis=eje))[5:-5, 5:-5]
        total = float(salto.sum())
        if total <= 1e-3 * salto.size:
            continue
        borrosa = np.apply_along_axis(lambda fila: np.convolve(fila, nucleo, "same"), eje, gris)
        salto_borroso = np.abs(np.diff(borrosa, axis=eje))[5:-5, 5:-5]
        perdido = float(np.maximum(0.0, salto - salto_borroso).sum())
        medidas.append((total - perdido) / total)
    # Sin cambios en ninguna dirección no hay con qué medir: no se avisa.
    return max(medidas) if medidas else 0.0


def luz_desigual(gris: np.ndarray) -> float:
    """Cociente entre la zona más iluminada y la más oscura de la luz de fondo.

    La luz se estima como en `digitalizar.quitar_luz`: el brillo desenfocado
    con un radio de un cuarto del lado, mucho mayor que cualquier dibujo de la
    tela. Se descarta el 10% del borde, donde el desenfoque se inventa la mitad
    de la ventana, y se comparan los percentiles 5 y 95.
    """
    luz = desenfocar(gris, max(gris.shape) * 0.25)
    alto, ancho = luz.shape
    m = int(min(alto, ancho) * 0.1)
    if m:
        luz = luz[m:-m, m:-m]
    bajo, alto_ = np.percentile(luz, [5, 95])
    return float(alto_ / max(bajo, 1e-3))


def _raya(recorte: Image.Image) -> Image.Image:
    """Mosaico de una raya, la fotografíe el usuario en vertical o en horizontal.

    `medir_rayas` espera las rayas en vertical: mide el perfil de las columnas.
    Una raya horizontal deja ese perfil plano y no encuentra período. Se mira en
    qué dirección varía más el brillo medio y, si es a lo alto, se gira antes.
    El mosaico sale siempre con la raya vertical, que es como se coloca en la
    prenda: la veta de cada pieza la gira después.
    """
    gris = _gris(recorte)
    if gris.mean(axis=1).std() > gris.mean(axis=0).std():
        recorte = recorte.transpose(Image.Transpose.ROTATE_90)

    medida = dig.medir_rayas(recorte)
    if medida["periodo_px"] is None:
        raise ErrorDeMotor(
            "No encuentro rayas que se repitan en la foto. Si la tela es de rayas, "
            "haz la foto de frente y con al menos tres rayas de cada color; si no, "
            "elige «estampada»."
        )
    return dig.muestra_rayas(dig.exponer_con_su_blanco(medida))


def _gris(imagen: Image.Image) -> np.ndarray:
    return (np.asarray(imagen.convert("RGB"), dtype=np.float32) / 255.0) @ dig.LUMINANCIA


__all__ = [
    "BORROSIDAD_MAXIMA",
    "JUNTA_MAXIMA",
    "LADO",
    "LADO_MINIMO",
    "LUZ_DESIGUAL",
    "TIPOS",
    "TelaDigitalizada",
    "borrosidad",
    "centro",
    "digitalizar",
    "luz_desigual",
    "revisar_foto",
]
