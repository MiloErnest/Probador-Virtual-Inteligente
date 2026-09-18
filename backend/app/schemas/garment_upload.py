"""Contratos de la API para las prendas que sube el usuario."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.garment_upload import GarmentKind


class GarmentUploadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    kind: GarmentKind

    image_url: str | None = None
    #: La máscara se expone a propósito: verla es la única forma de entender
    #: por qué una prueba ha salido mal. Sin esto, un recorte defectuoso se
    #: confunde con un fallo del motor.
    mask_url: str | None = None

    mask_coverage: float | None
    width: int | None
    height: int | None

    #: El recorte no es de fiar. Se calcula al subir para poder avisar ANTES de
    #: que el usuario pruebe diez telas sobre una máscara rota.
    mask_warning: str | None = None

    created_at: datetime
    updated_at: datetime
