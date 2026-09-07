"""Proveedor de Gemini: traducción de respuestas y de errores.

QUE SE PRUEBA Y QUE NO
----------------------
NO se llama a la API de verdad. Cada llamada cuesta dinero y exigiría una
clave en el entorno de pruebas; una suite que gasta saldo es una suite que
nadie ejecuta.

Lo que sí se prueba es todo lo que está bajo nuestro control, que es donde
están los fallos que podemos cometer: sacar los bytes de la respuesta,
detectar un bloqueo por seguridad, y convertir cada error del SDK en un
mensaje que el usuario pueda entender. La respuesta del SDK se sustituye por
objetos con la misma forma.

Lo que NO cubren estas pruebas —que la petición sea la correcta y que el
modelo devuelva algo útil— solo se comprueba llamando de verdad, con clave y
facturación. Ver PROJECT_STATUS.md.
"""

from types import SimpleNamespace

import pytest
from google.genai import errors, types

from app.ai.gemini import GeminiTryOnProvider
from app.ai.provider import TryOnProviderError

IMAGEN_FALSA = b"\x89PNG\r\n\x1a\n bytes de una imagen"


def hacer_provider(respuesta=None, excepcion=None) -> GeminiTryOnProvider:
    """Construye el proveedor con su cliente sustituido por uno simulado."""
    provider = GeminiTryOnProvider(api_key="clave-de-prueba", model="modelo-de-prueba")

    def generate_content(**_kwargs):
        if excepcion is not None:
            raise excepcion
        return respuesta

    provider._client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    return provider


def respuesta_con_imagen(data: bytes = IMAGEN_FALSA):
    parte = SimpleNamespace(inline_data=SimpleNamespace(data=data, mime_type="image/png"))
    return SimpleNamespace(
        parts=[parte],
        text=None,
        candidates=[SimpleNamespace(finish_reason=types.FinishReason.STOP)],
    )


def respuesta_sin_imagen(texto: str | None = None, finish_reason=types.FinishReason.STOP):
    return SimpleNamespace(
        parts=[SimpleNamespace(inline_data=None)],
        text=texto,
        candidates=[SimpleNamespace(finish_reason=finish_reason)],
    )


# --- Configuración -----------------------------------------------------------


def test_a_missing_api_key_fails_immediately_with_instructions() -> None:
    """Mejor romper al construirlo que a mitad de una tarea de fondo."""
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiTryOnProvider(api_key="", model="da-igual")


def test_the_provider_name_records_the_model() -> None:
    # Acaba en la columna `provider`. La calidad varía mucho entre modelos,
    # así que hay que poder saber cuál generó cada resultado.
    provider = GeminiTryOnProvider(api_key="k", model="gemini-3.1-flash-image")

    assert provider.name == "gemini:gemini-3.1-flash-image"


# --- Camino feliz ------------------------------------------------------------


def test_the_generated_image_bytes_are_returned() -> None:
    provider = hacer_provider(respuesta=respuesta_con_imagen())

    assert provider.generate(person=b"foto", garment=b"prenda") == IMAGEN_FALSA


# --- Respuestas sin imagen ---------------------------------------------------


def test_a_safety_block_is_explained_not_swallowed() -> None:
    """Un bloqueo llega como 200 con la razón dentro, no como error.

    Sin mirar `finish_reason`, esto se vería como "respuesta vacía", que no le
    dice nada al usuario ni a quien depura.
    """
    provider = hacer_provider(
        respuesta=respuesta_sin_imagen(finish_reason=types.FinishReason.IMAGE_SAFETY)
    )

    with pytest.raises(TryOnProviderError, match="seguridad"):
        provider.generate(person=b"foto", garment=b"prenda")


def test_prohibited_content_is_reported() -> None:
    provider = hacer_provider(
        respuesta=respuesta_sin_imagen(finish_reason=types.FinishReason.PROHIBITED_CONTENT)
    )

    with pytest.raises(TryOnProviderError, match="no está permitido"):
        provider.generate(person=b"foto", garment=b"prenda")


def test_a_text_only_answer_becomes_a_useful_message() -> None:
    # El modelo a veces contesta explicando por qué no puede hacerlo.
    provider = hacer_provider(
        respuesta=respuesta_sin_imagen(texto="No puedo generar esa imagen.")
    )

    with pytest.raises(TryOnProviderError, match="fotografía"):
        provider.generate(person=b"foto", garment=b"prenda")


# --- Errores del servicio ----------------------------------------------------


def test_quota_exceeded_tells_the_user_where_to_look() -> None:
    error = errors.ClientError(429, {"error": {"message": "Quota exceeded"}})

    with pytest.raises(TryOnProviderError, match="cuota"):
        hacer_provider(excepcion=error).generate(person=b"f", garment=b"p")


def test_an_invalid_key_is_reported_as_such() -> None:
    error = errors.ClientError(403, {"error": {"message": "Permission denied"}})

    with pytest.raises(TryOnProviderError, match="clave"):
        hacer_provider(excepcion=error).generate(person=b"f", garment=b"p")


def test_a_server_error_invites_retrying_later() -> None:
    error = errors.ServerError(503, {"error": {"message": "Unavailable"}})

    with pytest.raises(TryOnProviderError, match="no está disponible"):
        hacer_provider(excepcion=error).generate(person=b"f", garment=b"p")


def test_an_unexpected_failure_does_not_leak_internals() -> None:
    """Un fallo de red no debe enseñarle al usuario una traza.

    El detalle va al log del servidor; en pantalla, algo accionable.
    """
    with pytest.raises(TryOnProviderError) as excinfo:
        hacer_provider(excepcion=OSError("conexión rechazada")).generate(
            person=b"f", garment=b"p"
        )

    assert "conexión rechazada" not in str(excinfo.value)


# --- Selección del proveedor -------------------------------------------------


def test_an_unknown_provider_name_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nunca caer al proveedor local en silencio.

    Creer que estás usando el modelo de pago cuando en realidad estás pegando
    imágenes con Pillow sería el peor error posible aquí.
    """
    from app.ai import get_try_on_provider
    from app.core.config import settings

    monkeypatch.setattr(settings, "AI_PROVIDER", "modelo-que-no-existe")

    with pytest.raises(ValueError, match="no corresponde a ningún proveedor"):
        get_try_on_provider()


def test_selecting_gemini_without_a_key_fails_with_instructions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ai import get_try_on_provider
    from app.core.config import settings

    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        get_try_on_provider()
