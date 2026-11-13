"""Contratos de la API para las prendas que sube el usuario."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.garment_upload import GarmentKind, GarmentStatus


class GarmentUploadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    kind: GarmentKind
    #: Solo `ready` se puede probar. Un boceto pasa por `pending` y
    #: `processing` mientras la IA genera su prenda: hay que sondear.
    status: GarmentStatus

    #: La prenda. En un boceto sin generar todavía, el propio dibujo.
    image_url: str | None = None
    #: El dibujo original. Nulo en una fotografía.
    sketch_url: str | None = None
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

    # --- Solo en un boceto ---
    error_message: str | None = None
    #: Coincidencia de la silueta de la prenda con la del dibujo, de 0 a 1.
    similarity: float | None = None
    #: Si la silueta se aparta del dibujo, qué hacer. Nulo si se parece.
    similarity_warning: str | None = None
    tokens_used: int | None = None

    created_at: datetime
    updated_at: datetime
