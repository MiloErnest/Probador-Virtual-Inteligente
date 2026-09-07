"""Contratos de la API para diseños generados (Fase 2)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.design import DesignStatus

# Tope del texto. Alto para no cortar la creatividad, pero acotado: sin
# límite, una descripción enorme se convierte en coste y latencia cuando el
# proveedor sea de pago.
MAX_PROMPT = 1000


class DesignCreate(BaseModel):
    prompt: str = Field(
        min_length=3,
        max_length=MAX_PROMPT,
        description="Describe la prenda que quieres. Ej: «vestido largo rojo de gala»",
    )


class DesignRefine(BaseModel):
    """Iteración sobre un diseño existente.

    Solo lleva la instrucción del cambio; el texto original se hereda del
    diseño padre. Así el usuario escribe «hazlo más corto» en vez de repetir
    la descripción entera.
    """

    refinement: str = Field(
        min_length=3,
        max_length=MAX_PROMPT,
        description="Qué cambiar. Ej: «que sea azul y más corto»",
    )


class DesignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    prompt: str
    refinement: str | None = None
    parent_id: int | None = None
    status: DesignStatus
    # Igual que en el resto del proyecto: la base guarda `image_key`, la API
    # expone `image_url`.
    image_url: str | None = None
    error_message: str | None = None
    provider: str | None = None
    created_at: datetime
    updated_at: datetime
