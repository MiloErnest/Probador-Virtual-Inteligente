"""Contrato de un proveedor de prueba virtual.

POR QUÉ ESTE PROTOCOL EXISTE AHORA Y NO ANTES
---------------------------------------------
Hasta la Fase 1, `app/ai/` estaba vacío a propósito, con esta nota en
CLAUDE.md: no definir la interfaz hasta tener una implementación real, porque
una interfaz escrita de memoria casi siempre es la equivocada.

Ya existe esa implementación (`LocalPreviewProvider`), así que el contrato se
escribe a partir de algo que funciona. Aun así es un contrato JOVEN: solo lo
cumple una clase. Se dará por bueno cuando lo cumpla el segundo proveedor, el
de IA de verdad, y es probable que algo cambie entonces.

Por eso la superficie es deliberadamente mínima —un método— en vez de
adelantarse a lo que un proveedor remoto "seguramente" necesitará.

SÍNCRONO A PROPÓSITO
--------------------
`generate` bloquea. Una llamada a un modelo de try-on tarda de segundos a
minutos, así que nunca se invoca dentro del ciclo de una petición HTTP: corre
en una tarea de fondo (ver `app/services/try_on_session.py`). Mantenerlo
síncrono encaja con el resto del proyecto, que usa SQLAlchemy síncrono.
"""

from typing import Protocol


class TryOnProviderError(Exception):
    """El proveedor no pudo generar el resultado.

    Su mensaje acaba guardado en `try_on_sessions.error_message` y se le
    enseña al usuario, así que debe ser presentable: nada de trazas ni de
    detalles internos.
    """


class TryOnProvider(Protocol):
    """Lo mínimo que debe saber hacer un proveedor de prueba virtual."""

    # Se guarda en `try_on_sessions.provider`. Permite saber qué generó cada
    # resultado, comparar proveedores y reprocesar lo que falló con otro.
    name: str

    def generate(self, *, person: bytes, garment: bytes) -> bytes:
        """Recibe la foto de la persona y la de la prenda; devuelve la imagen
        resultante en PNG.

        Lanza `TryOnProviderError` si no puede completarla.
        """
        ...
