"""Vestir a una persona con una prenda del taller.

EL CAMINO
---------
1. **Encontrar a la persona** en la foto con el analizador (`partes.py`) y
   encuadrarla. El modelo trabaja a 864 px de alto: si se le manda la foto
   entera de alguien que ocupa un tercio, la prenda sale con un tercio de esos
   píxeles. Encuadrada, la persona llena el cuadro.
2. **Vestirla** con el modelo configurado (`proveedor.py`).
3. **Conservar a la persona** (`conservar.py`): de la imagen generada solo
   entra la ropa que se prueba y la piel que esa ropa cambia. Lo demás son los
   píxeles originales, a la resolución original.

Si el modelo no está activado se sabe ANTES de analizar nada: ni se descarga
el analizador ni se gasta cuota para acabar diciendo que no hay modelo.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from PIL import Image

from app.models.try_on import GarmentCategory
from app.probador import partes as P
from app.probador.conservar import zona_editable
from app.probador.proveedor import ModeloDePrueba, PeticionDePrueba, modelo_configurado
from app.textil.errores import ErrorDeMotor

#: Lado mayor al que se analizan las imágenes y se decide la zona. La zona se
#: difumina después, así que no necesita la resolución completa.
LADO_DE_ANALISIS = 1024

#: Proporción del cuadro que se le manda al modelo: la suya, 576 × 864.
PROPORCION = 2 / 3

#: Aire alrededor de la persona al encuadrarla, en fracción de su alto.
AIRE = 0.06

#: Menos que esto de persona en la foto, y no hay a quién vestir.
PERSONA_MINIMA = 0.02

#: Menos que esto de prenda nueva en la imagen generada, y el modelo no la ha
#: puesto: mejor decirlo que devolver la foto original como si fuera un
#: resultado.
PRENDA_MINIMA = 0.01

#: A partir de esta fracción de la foto cambiada fuera de la prenda, se avisa.
DESCARTE_A_AVISAR = 0.01


@dataclass(frozen=True)
class PersonaVestida:
    imagen: Image.Image
    proveedor: str
    #: Qué parte de la foto viene del modelo. El resto es la foto original.
    editado: float
    #: Qué parte de la foto había cambiado el modelo fuera de la prenda, y se
    #: ha deshecho.
    descartado: float
    aviso: str | None


def vestir_persona(
    persona: Image.Image,
    prenda: Image.Image,
    categoria: GarmentCategory,
    *,
    variante: int = 0,
    modelo: ModeloDePrueba | None = None,
    etiquetar: Callable[[Image.Image, tuple[int, int]], np.ndarray] | None = None,
) -> PersonaVestida:
    """Devuelve la foto de `persona` con `prenda` puesta.

    `modelo` y `etiquetar` se inyectan en las pruebas automáticas, que no
    pueden llamar a Hugging Face ni descargar el analizador.
    """
    modelo = modelo or modelo_configurado()
    etiquetar = etiquetar or P.etiquetar
    persona = persona.convert("RGB")

    # 1. Encontrar a la persona y encuadrarla.
    tamano = _reducido(persona.size, LADO_DE_ANALISIS)
    figura = etiquetar(persona, tamano) != P.FONDO
    if figura.mean() < PERSONA_MINIMA:
        raise ErrorDeMotor(
            "No se ve a ninguna persona en la foto. Hace falta una foto de cuerpo "
            "entero o de medio cuerpo, con la persona bien visible."
        )
    escala = persona.width / tamano[0]
    caja = _encuadre(figura, escala, persona.size)
    recorte = persona.crop(caja)

    # 2. Vestirla.
    generada = modelo.vestir(
        PeticionDePrueba(persona=recorte, prenda=prenda, categoria=categoria, variante=variante)
    )
    if abs(generada.width / generada.height - recorte.width / recorte.height) > 0.03:
        raise ErrorDeMotor(
            "El modelo ha devuelto una imagen con otro encuadre, y no se puede "
            "superponer a tu foto sin deformarla."
        )

    # 3. Conservar a la persona.
    trabajo = _reducido(recorte.size, LADO_DE_ANALISIS)
    persona_px = np.asarray(recorte.resize(trabajo, Image.Resampling.LANCZOS), dtype=np.float32)
    generada_px = np.asarray(generada.resize(trabajo, Image.Resampling.LANCZOS), dtype=np.float32)
    zona = zona_editable(
        persona_px, generada_px, etiquetar(recorte, trabajo), etiquetar(generada, trabajo), categoria
    )
    if zona.prenda_nueva < PRENDA_MINIMA:
        raise ErrorDeMotor(
            "El modelo no ha llegado a colocar la prenda. Suele pasar con posturas muy "
            "cerradas o con la prenda muy tapada; prueba con otra foto."
        )

    import cv2

    alfa = cv2.resize(zona.alfa, recorte.size, interpolation=cv2.INTER_LINEAR)[..., None]
    grande = np.asarray(generada.resize(recorte.size, Image.Resampling.LANCZOS), dtype=np.float32)
    original = np.asarray(recorte, dtype=np.float32)
    mezcla = original * (1.0 - alfa) + grande * alfa

    salida = persona.copy()
    salida.paste(Image.fromarray(np.clip(mezcla + 0.5, 0, 255).astype(np.uint8)), caja[:2])

    total = persona.width * persona.height
    editado = float(alfa.sum()) / total
    descartado = zona.descartado * (recorte.width * recorte.height) / total
    return PersonaVestida(
        imagen=salida,
        proveedor=modelo.nombre,
        editado=editado,
        descartado=descartado,
        aviso=_aviso(descartado),
    )


def _aviso(descartado: float) -> str | None:
    if descartado < DESCARTE_A_AVISAR:
        return None
    return (
        f"El modelo también había cambiado un {descartado:.0%} de tu foto fuera de "
        "la prenda (fondo, cara, manos u otra ropa). Se ha deshecho: ahí ves tu foto "
        "original."
    )


def _reducido(tamano: tuple[int, int], lado: int) -> tuple[int, int]:
    ancho, alto = tamano
    escala = min(1.0, lado / max(ancho, alto))
    return max(8, round(ancho * escala)), max(8, round(alto * escala))


def _encuadre(
    figura: np.ndarray, escala: float, tamano: tuple[int, int]
) -> tuple[int, int, int, int]:
    """Caja de la persona en la foto original, con aire y en la proporción del modelo."""
    filas = np.nonzero(figura.any(axis=1))[0]
    columnas = np.nonzero(figura.any(axis=0))[0]
    x0, x1 = columnas[0] * escala, (columnas[-1] + 1) * escala
    y0, y1 = filas[0] * escala, (filas[-1] + 1) * escala

    aire = AIRE * (y1 - y0)
    x0, x1, y0, y1 = x0 - aire, x1 + aire, y0 - aire, y1 + aire
    ancho, alto = x1 - x0, y1 - y0
    if ancho / alto < PROPORCION:
        ancho = alto * PROPORCION
    else:
        alto = ancho / PROPORCION
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

    limite_x, limite_y = tamano
    ancho, alto = min(ancho, limite_x), min(alto, limite_y)
    x0 = min(max(0.0, cx - ancho / 2), limite_x - ancho)
    y0 = min(max(0.0, cy - alto / 2), limite_y - alto)
    return round(x0), round(y0), round(x0 + ancho), round(y0 + alto)
