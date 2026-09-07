"""Proveedores de prueba virtual.

Punto único donde se elige la implementación, igual que `get_storage()` hace
con el almacenamiento. Añadir el proveedor de IA de verdad consistirá en
escribir su clase y añadir una rama aquí; ni las rutas, ni los servicios, ni
la base de datos cambian.
"""

from app.ai.gemini import GeminiTryOnProvider
from app.ai.local_preview import LocalPreviewProvider
from app.ai.provider import TryOnProvider, TryOnProviderError
from app.core.config import settings

__all__ = [
    "TryOnProvider",
    "TryOnProviderError",
    "LocalPreviewProvider",
    "GeminiTryOnProvider",
    "get_try_on_provider",
]


def get_try_on_provider() -> TryOnProvider:
    """Devuelve el proveedor configurado en `AI_PROVIDER`.

    Un valor desconocido falla de inmediato y con nombres concretos, en vez
    de caer en silencio al proveedor local: creer que estás usando el modelo
    de IA cuando en realidad estás componiendo imágenes sería el peor de los
    errores posibles aquí.
    """
    nombre = settings.AI_PROVIDER.strip().lower()

    if nombre in ("local", "local-preview"):
        return LocalPreviewProvider()

    if nombre == "gemini":
        # Se construye en cada llamada, no una sola vez al importar: así un
        # cambio de clave o de modelo en el .env surte efecto reiniciando la
        # aplicación, sin tener que razonar sobre estado global.
        return GeminiTryOnProvider(
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
            timeout_seconds=settings.GEMINI_TIMEOUT_SECONDS,
        )

    raise ValueError(
        f"AI_PROVIDER={settings.AI_PROVIDER!r} no corresponde a ningún proveedor. "
        "Valores admitidos: 'local', 'gemini'."
    )
