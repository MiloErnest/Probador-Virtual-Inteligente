"""Contrato de un analizador corporal a partir de una fotografía (Fase 3).

Igual que `TryOnProvider` y `DesignProvider`: una interfaz mínima para que la
implementación real —MediaPipe, o un servicio remoto— entre sin tocar nada
más.

POR QUE DEVUELVE MEDIDAS Y NO PUNTOS DE POSE
--------------------------------------------
Un detector de pose devuelve coordenadas de articulaciones. Convertir eso en
centímetros exige conocer la distancia a la cámara y la altura real de la
persona, y es donde está la dificultad de verdad.

Ese trabajo pertenece al proveedor, no al servicio que lo llama: si el
contrato fuera «devuelve landmarks», cada consumidor tendría que repetir la
conversión, y cambiar de proveedor obligaría a reescribirla. Devolviendo
medidas, el dominio habla en las unidades que usa el tallaje.
"""

from dataclasses import dataclass
from typing import Protocol


class BodyAnalysisError(Exception):
    """No se pudieron estimar las medidas.

    Su mensaje se le enseña al usuario, así que debe ser presentable: lo más
    útil suele ser decirle cómo hacer mejor la foto.
    """


@dataclass(frozen=True)
class BodyMeasurements:
    """Medidas estimadas, en centímetros. Todas opcionales.

    Un proveedor puede estimar unas y otras no —la longitud de entrepierna
    necesita ver las piernas enteras, por ejemplo—. Devolver None es
    preferible a inventar un número: la recomendación de talla ya sabe
    trabajar con lo que haya, y un valor falso daría una talla falsa con
    aspecto de certeza.
    """

    height_cm: float | None = None
    chest_cm: float | None = None
    waist_cm: float | None = None
    hips_cm: float | None = None
    inseam_cm: float | None = None

    # Entre 0 y 1. Cuánto se fía el proveedor de lo que acaba de estimar.
    # La interfaz lo usa para avisar de que estas medidas son aproximadas.
    confidence: float = 0.0


class BodyAnalysisProvider(Protocol):
    """Lo mínimo que debe saber hacer un analizador corporal."""

    name: str

    def analyse(self, *, photo: bytes, height_cm: float | None = None) -> BodyMeasurements:
        """Estima las medidas de la persona que aparece en la fotografía.

        `height_cm` es la altura real, si el usuario la sabe. Es la referencia
        que convierte proporciones en centímetros: sin ella, cualquier
        estimación es una proporción multiplicada por una altura supuesta, y
        el error se propaga a todas las medidas.

        Lanza `BodyAnalysisError` si no puede completarlo.
        """
        ...
