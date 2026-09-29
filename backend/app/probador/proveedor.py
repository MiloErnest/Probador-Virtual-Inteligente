"""El contrato del modelo que viste a la persona, y el selector.

Es el único sitio que decide qué modelo corre, igual que `motor_para` en el
motor textil. Un valor desconocido falla en voz alta: creer que se está usando
un modelo cuando corre otro ya pasó una vez en este proyecto.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PIL import Image

from app.core.config import settings
from app.models.try_on import GarmentCategory
from app.textil.errores import ErrorDeMotor


@dataclass(frozen=True)
class PeticionDePrueba:
    #: La persona, ya encuadrada: la caja que la contiene, no la foto entera.
    persona: Image.Image
    #: La prenda sobre blanco (`prenda.recortar_prenda`).
    prenda: Image.Image
    categoria: GarmentCategory
    #: Número que decide la semilla del modelo: el de la propia prueba.
    #:
    #: El modelo es determinista, y con una semilla fija repetir una prueba
    #: daba EXACTAMENTE la misma imagen. Le pasó al usuario: el modelo se
    #: inventó un cordón azul colgando del cuello, y volver a probar devolvía
    #: el mismo cordón. Con el número de la prueba, cada intento es otra
    #: variante, y sigue siendo reproducible: el número queda guardado.
    #:
    #: Se descartó contar los intentos anteriores de la misma combinación: el
    #: usuario borra pruebas, y al borrar la mala la cuenta bajaba y volvía la
    #: misma imagen.
    variante: int = 0


class ModeloDePrueba(Protocol):
    """Un modelo de prueba virtual: persona + prenda → persona con la prenda."""

    nombre: str

    def vestir(self, peticion: PeticionDePrueba) -> Image.Image: ...


def modelo_configurado() -> ModeloDePrueba:
    """El modelo que toca según `VTO_PROVIDER`, o por qué no hay ninguno."""
    valor = settings.VTO_PROVIDER.strip().lower()

    if valor in ("", "none"):
        raise ErrorDeMotor(
            "El probador no está activado. Pon VTO_PROVIDER=fashn en backend/.env: "
            "es gratuito, y funciona con la cuota diaria de Hugging Face."
        )

    if valor == "fashn":
        from app.probador.fashn import ModeloFashn

        return ModeloFashn()

    raise ErrorDeMotor(
        f"VTO_PROVIDER='{settings.VTO_PROVIDER}' no se reconoce. "
        "Los valores válidos son 'none' y 'fashn'."
    )
