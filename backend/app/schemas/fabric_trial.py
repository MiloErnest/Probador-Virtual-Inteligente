"""Contratos de la API para las pruebas de tela."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.fabric_trial import TrialMethod, TrialStatus


class TrialCreate(BaseModel):
    garment_upload_id: int
    fabric_id: int

    #: Con qué motor. Nulo = lo decide el servidor según el tipo de prenda:
    #: una fotografía tiene luz que reutilizar, un boceto no.
    method: TrialMethod | None = None

    #: Escala del estampado. Nulo = la que traiga la tela en su ficha.
    repeat_across: int | None = Field(default=None, ge=1, le=40)


class TrialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    garment_upload_id: int
    fabric_id: int

    status: TrialStatus
    method: TrialMethod
    repeat_across: int

    output_image_url: str | None = None
    error_message: str | None
    provider: str | None

    #: Nulo en el motor determinista, que no cuesta nada. Que la diferencia se
    #: vea en la galería es intencionado.
    tokens_used: int | None
    duration_ms: int | None

    #: Algo que conviene saber del resultado sin ser un error: por ejemplo que
    #: la prenda no tenía sombras y la tela ha salido plana.
    notice: str | None = None

    created_at: datetime
    updated_at: datetime
