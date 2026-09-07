"""Contratos de salida de la API para sesiones de prueba virtual.

Solo lectura en la Etapa 1: el schema de creación llegará junto con la
integración del proveedor de IA.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.try_on_session import TryOnStatus


class TryOnSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    # Uno de los dos, nunca ambos: la prueba parte del catálogo o de un
    # diseño propio.
    garment_id: int | None = None
    design_id: int | None = None
    status: TryOnStatus
    input_image_url: str | None = None
    output_image_url: str | None = None
    error_message: str | None = None
    provider: str | None = None
    created_at: datetime
    updated_at: datetime
