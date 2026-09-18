"""Contrato de los motores que visten una prenda con una tela.

DOS MOTORES, Y NO COMPITEN: SE REPARTEN EL TRABAJO
--------------------------------------------------
- `MotorRetexturizado` reutiliza la luz de la fotografía. Gratis, instantáneo,
  y **determinista**: la misma prenda con la misma tela da siempre el mismo
  resultado. Es lo que hace que comparar cuatro telas lado a lado signifique
  algo, porque lo único que cambia entre las cuatro es la tela.
- `MotorOpenAI` genera la imagen con un modelo. Cuesta dinero por llamada y no
  es determinista, pero es la única vía para un boceto: un dibujo de líneas no
  tiene sombras que reutilizar.

EL SELECTOR FALLA EN VOZ ALTA
-----------------------------
Si se pide el motor de IA y no está configurado, esto lanza un error con lo
que hay que hacer. NO cae al motor determinista en silencio.

Esa regla viene de un error cometido en este mismo proyecto: llegó a haber un
proveedor «simulado» que se hacía pasar por IA, y durante semanas el proyecto
dijo tener funciones de inteligencia artificial que en realidad eran píxeles
pegados con Pillow. Creer que estás usando el modelo cuando no lo estás es el
peor fallo posible aquí, porque no se nota hasta que alguien pregunta.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PIL import Image

from app.core.config import settings
from app.models.fabric_trial import TrialMethod
from app.models.garment_upload import GarmentKind
from app.textil.errores import ErrorDeMotor
from app.textil.retexturizar import retexturizar, vestir_boceto


@dataclass(frozen=True)
class PeticionDeTela:
    """Todo lo que un motor necesita para vestir una prenda."""

    prenda: Image.Image
    mascara: Image.Image
    caja: tuple[int, int, int, int]
    tipo: GarmentKind

    #: Mosaico de la tela. Imprescindible para el retexturizado; el motor
    #: generativo lo ignora, porque a él se le describe la tela con palabras.
    mosaico: Image.Image | None
    #: Cómo se llama la tela y de qué es. Es lo que se le cuenta al modelo.
    descripcion: str
    repeticiones: int


@dataclass(frozen=True)
class ResultadoDeTela:
    imagen: Image.Image
    proveedor: str
    #: Tokens facturados. Nulo cuando el motor no cuesta dinero.
    tokens: int | None = None
    #: Algo que el usuario debería saber del resultado, sin ser un error.
    aviso: str | None = None


class MotorDeTela(Protocol):
    """Contrato mínimo de un motor."""

    nombre: str

    def aplicar(self, peticion: PeticionDeTela) -> ResultadoDeTela:
        """Devuelve la prenda vestida con la tela."""
        ...


#: Por debajo de este relieve, la prenda no tenía sombras que reutilizar.
#: Medido sobre la razón de luz dentro de la máscara.
CONTRASTE_SOSO = 0.045


class MotorRetexturizado:
    """Reutiliza la luz de la fotografía. No es inteligencia artificial."""

    nombre = "retexturizado-local"

    def aplicar(self, peticion: PeticionDeTela) -> ResultadoDeTela:
        if peticion.mosaico is None:
            raise ErrorDeMotor(
                "Esta tela no tiene mosaico cargado, así que no se puede estampar. "
                "Súbele una imagen de la tela desde el catálogo."
            )

        # Un boceto y una fotografía necesitan caminos distintos, y no es un
        # detalle: la foto TIENE luz que reutilizar y el dibujo no. Aplicarle a
        # un boceto el camino de la foto da un recorte de papel pintado.
        if peticion.tipo is GarmentKind.SKETCH:
            salida = vestir_boceto(
                peticion.prenda,
                peticion.mascara,
                peticion.mosaico,
                repeticiones=peticion.repeticiones,
                caja=peticion.caja,
            )
            return ResultadoDeTela(
                imagen=salida.imagen,
                proveedor=f"{self.nombre}-boceto",
                aviso=(
                    "Tu dibujo se conserva tal cual y la tela rellena el interior. El "
                    "volumen es aproximado: un boceto no tiene sombras de las que "
                    "deducirlo. Si quieres una imagen fotorrealista, usa el motor de "
                    "IA — pero ten en cuenta que reinterpreta el diseño."
                ),
            )

        salida = retexturizar(
            peticion.prenda,
            peticion.mascara,
            peticion.mosaico,
            repeticiones=peticion.repeticiones,
            caja=peticion.caja,
        )

        aviso = None
        if salida.contraste < CONTRASTE_SOSO:
            aviso = (
                "Esta fotografía apenas tiene sombras, así que la tela sale plana: no "
                "hay pliegues que reutilizar. Con una foto menos iluminada de frente "
                "se nota mucho la diferencia."
            )

        return ResultadoDeTela(imagen=salida.imagen, proveedor=self.nombre, aviso=aviso)


def motor_para(metodo: TrialMethod) -> MotorDeTela:
    """Devuelve el motor que toca, o explica por qué no se puede.

    Es el único sitio del proyecto que decide qué motor corre. Igual que
    `get_current_user` es el único que convierte un token en usuario.
    """
    if metodo is TrialMethod.RETEXTURE:
        return MotorRetexturizado()

    if metodo is TrialMethod.AI:
        proveedor = settings.AI_PROVIDER.strip().lower()

        if proveedor in ("", "none"):
            raise ErrorDeMotor(
                "El motor de IA no está activado. Para usarlo, pon AI_PROVIDER=openai "
                "y tu OPENAI_API_KEY en backend/.env. Ten en cuenta que cada imagen "
                "generada se cobra."
            )

        if proveedor == "openai":
            # Import aquí y no arriba: el SDK de OpenAI tarda en cargar y no
            # tiene sentido pagarlo en cada arranque de quien no lo use.
            from app.textil.openai_provider import MotorOpenAI

            return MotorOpenAI()

        # Un valor desconocido NO cae al motor local. Ver la cabecera.
        raise ErrorDeMotor(
            f"AI_PROVIDER='{settings.AI_PROVIDER}' no se reconoce. "
            "Los valores válidos son 'none' y 'openai'."
        )

    raise ErrorDeMotor(f"Motor desconocido: {metodo}.")
