"""Contrato de un generador de diseños de prenda a partir de texto (Fase 2).

Se separa de `TryOnProvider` a propósito, aunque los dos generen imágenes.
Son problemas distintos: aquí se parte de una DESCRIPCIÓN y no hay ninguna
persona a la que respetar. Fundirlos en una sola interfaz obligaría a que
cada implementación aceptara parámetros que no usa.

Que hoy un mismo servicio pueda cumplir los dos contratos no es razón para
unirlos: eso es una coincidencia del proveedor, no del dominio.
"""

from typing import Protocol


class DesignProviderError(Exception):
    """El proveedor no pudo generar el diseño.

    Su mensaje se guarda en `designs.error_message` y se le enseña al
    usuario, así que debe ser presentable.
    """


class DesignProvider(Protocol):
    """Lo mínimo que debe saber hacer un generador de diseños."""

    name: str

    def generate(
        self,
        *,
        prompt: str,
        base_image: bytes | None = None,
        refinement: str | None = None,
    ) -> bytes:
        """Genera la imagen de una prenda y la devuelve en PNG.

        `base_image` y `refinement` solo llegan cuando se está ITERANDO sobre
        un diseño anterior: la imagen de partida y qué hay que cambiar de
        ella. En una generación desde cero ambos son None.

        Un proveedor que no sepa iterar puede ignorar `base_image` y tratar la
        petición como una generación nueva; lo que no debe hacer es fallar,
        porque iterar es parte del flujo normal.

        Lanza `DesignProviderError` si no puede completarla.
        """
        ...
