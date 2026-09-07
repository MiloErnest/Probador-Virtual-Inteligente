"""Proveedor de prueba virtual con Gemini («Nano Banana») de Google.

POR QUE ESTE MODELO Y NO OTRO
-----------------------------
Una prueba virtual necesita DOS imágenes de entrada: la persona y la prenda
concreta del catálogo. Casi todos los modelos de imagen aceptan una sola
imagen más un texto, y con eso solo se puede *inventar* una prenda a partir
de una descripción, no vestir a alguien con la prenda que eligió.

Los modelos Gemini de imagen aceptan varias imágenes de referencia en una
misma petición, así que se les puede dar la foto y la prenda y pedir la
composición. Por eso son de los pocos servicios generalistas que valen aquí.

COSTE
-----
Se paga por imagen generada y **el nivel gratuito de la API de Gemini no
incluye generación de imágenes**: hay que activar facturación en el proyecto
de Google. Orden de magnitud a fecha de integración: unos 4 céntimos de dólar
por imagen con los modelos flash. Cada prueba que lance un usuario cuesta
dinero real, y hoy no hay límite de peticiones (limitación #8).

MARCA DE AGUA
-------------
Google incrusta una marca invisible (SynthID) en todo lo que genera. No se
puede desactivar. Es correcto que así sea —el resultado es una imagen
sintética— pero conviene saberlo si el proyecto se presenta como trabajo
académico.

LO QUE ESTA CLASE NO HACE
-------------------------
No reintenta. Si la llamada falla, la prueba queda en `failed` y el usuario
puede volver a lanzarla. Reintentar automáticamente algo que se cobra por
uso, sin control de gasto, es una forma rápida de vaciar una cuenta.
"""

import logging

from google import genai
from google.genai import errors, types

from app.ai.provider import TryOnProviderError

logger = logging.getLogger("app.ai.gemini")

# Instrucción que acompaña a las dos imágenes. Es la pieza que más influye en
# la calidad del resultado, así que está aquí y no repartida por el código.
#
# Las tres reglas explícitas responden a los fallos típicos de estos modelos:
# cambiar la cara de la persona, alterar el fondo, o devolver la prenda sola
# en lugar de la persona vestida.
TRY_ON_PROMPT = (
    "Eres un asistente de prueba virtual de ropa. "
    "La PRIMERA imagen es la fotografía de una persona. "
    "La SEGUNDA imagen es una prenda de ropa. "
    "Genera una única imagen fotorrealista de esa misma persona vistiendo esa "
    "misma prenda.\n"
    "Reglas obligatorias:\n"
    "1. Conserva sin cambios el rostro, el peinado, el tono de piel, la postura "
    "y la complexión de la persona.\n"
    "2. Conserva el fondo y la iluminación de la fotografía original.\n"
    "3. Respeta el color, el estampado, la textura y el corte de la prenda; "
    "adáptala al cuerpo con pliegues y sombras creíbles.\n"
    "Devuelve solamente la imagen resultante."
)

# Formato de salida. PNG por coherencia con el resto del proyecto: el
# almacenamiento guarda los resultados con extensión .png.
OUTPUT_MIME_TYPE = "image/png"


class GeminiTryOnProvider:
    """Prueba virtual con los modelos de imagen de Gemini. Cumple `TryOnProvider`."""

    def __init__(self, api_key: str, model: str, timeout_seconds: int = 120) -> None:
        if not api_key:
            # Falla al construirlo, no en mitad de una tarea de fondo: así el
            # error sale en el arranque o en el primer intento, con un mensaje
            # que dice exactamente qué falta.
            raise ValueError(
                "Falta GEMINI_API_KEY. Consíguela en https://aistudio.google.com/apikey "
                "y ponla en backend/.env (nunca en el código)."
            )

        self.model = model
        # `name` acaba en la columna `provider` de cada prueba. Incluye el
        # modelo porque la calidad varía mucho entre ellos y conviene saber
        # cuál generó cada resultado.
        self.name = f"gemini:{model}"

        self._client = genai.Client(
            api_key=api_key,
            # El SDK espera milisegundos. Sin timeout, una llamada colgada
            # dejaría la prueba en `processing` indefinidamente.
            http_options=types.HttpOptions(timeout=timeout_seconds * 1000),
        )

    def generate(self, *, person: bytes, garment: bytes) -> bytes:
        try:
            response = self._client.models.generate_content(
                model=self.model,
                # El orden importa: el prompt se refiere a "la primera imagen"
                # y "la segunda imagen".
                contents=[
                    TRY_ON_PROMPT,
                    types.Part.from_bytes(data=person, mime_type="image/png"),
                    types.Part.from_bytes(data=garment, mime_type="image/png"),
                ],
                config=types.GenerateContentConfig(
                    # Sin esto el modelo puede contestar con texto describiendo
                    # la imagen en lugar de generarla.
                    response_modalities=[types.Modality.IMAGE],
                    image_config=types.ImageConfig(
                        output_mime_type=OUTPUT_MIME_TYPE,
                        # Imprescindible: el caso de uso es literalmente
                        # generar imágenes de personas adultas. Con el valor
                        # por defecto, el modelo puede negarse.
                        person_generation="ALLOW_ADULT",
                    ),
                ),
            )
        except errors.ClientError as exc:
            # 4xx: culpa nuestra o de la configuración. El detalle va al log;
            # al usuario se le dice algo accionable.
            logger.warning("Gemini rechazó la petición: %s", exc)
            raise TryOnProviderError(self._client_error_message(exc)) from exc
        except errors.ServerError as exc:
            logger.warning("Gemini no está disponible: %s", exc)
            raise TryOnProviderError(
                "El servicio de imagen no está disponible ahora mismo. "
                "Vuelve a intentarlo en unos minutos."
            ) from exc
        except errors.APIError as exc:
            logger.exception("Error de la API de Gemini.")
            raise TryOnProviderError(
                "No se pudo contactar con el servicio de imagen."
            ) from exc
        except Exception as exc:  # noqa: BLE001 - red, DNS, timeouts del cliente
            logger.exception("Fallo inesperado llamando a Gemini.")
            raise TryOnProviderError(
                "No se pudo generar el resultado. Vuelve a intentarlo."
            ) from exc

        return self._extract_image(response)

    # --- Interno ---

    def _extract_image(self, response: types.GenerateContentResponse) -> bytes:
        """Saca los bytes de la imagen, o explica por qué no hay ninguna."""
        # Un modelo que se niega devuelve 200 con la razón dentro. Sin mirar
        # `finish_reason`, un bloqueo por seguridad se vería como "respuesta
        # vacía", que no le dice nada a nadie.
        motivo = self._blocking_reason(response)
        if motivo is not None:
            raise TryOnProviderError(motivo)

        for part in response.parts or []:
            inline = getattr(part, "inline_data", None)
            if inline is not None and inline.data:
                return inline.data

        # Devolvió texto en lugar de imagen: suele ser el modelo explicando
        # por qué no puede hacerlo.
        explicacion = (response.text or "").strip()
        if explicacion:
            logger.warning("Gemini respondió con texto y no con imagen: %s", explicacion[:300])

        raise TryOnProviderError(
            "El modelo no devolvió ninguna imagen. Prueba con otra fotografía, "
            "preferiblemente de cuerpo entero, bien iluminada y de frente."
        )

    def _blocking_reason(self, response: types.GenerateContentResponse) -> str | None:
        """Traduce un bloqueo del modelo a un mensaje presentable."""
        for candidate in response.candidates or []:
            razon = candidate.finish_reason
            if razon in (types.FinishReason.SAFETY, types.FinishReason.IMAGE_SAFETY):
                return (
                    "El servicio bloqueó esta imagen por sus filtros de seguridad. "
                    "Prueba con otra fotografía."
                )
            if razon == types.FinishReason.PROHIBITED_CONTENT:
                return "El contenido de la imagen no está permitido por el servicio."
        return None

    def _client_error_message(self, exc: errors.ClientError) -> str:
        codigo = getattr(exc, "code", None)
        if codigo == 429:
            return (
                "Se ha superado la cuota del servicio de imagen. "
                "Revisa los límites y la facturación de tu cuenta de Google."
            )
        if codigo in (401, 403):
            return (
                "La clave de la API no es válida o no tiene permisos. "
                "Revisa GEMINI_API_KEY y que la facturación esté activada."
            )
        return "El servicio de imagen rechazó la petición."
