"""Contratos de la API del probador: fotos de persona y pruebas sobre ellas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.fabric_trial import TrialStatus
from app.models.try_on import GarmentCategory


class PersonPhotoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    image_url: str | None = None
    width: int
    height: int
    created_at: datetime
    updated_at: datetime


class TryOnCreate(BaseModel):
    person_photo_id: int

    #: La prenda sale de UNA de estas dos. Con una prueba de tela se usa la
    #: imagen ya generada, no una nueva.
    fabric_trial_id: int | None = None
    garment_upload_id: int | None = None

    category: GarmentCategory = GarmentCategory.TOP

    @model_validator(mode="after")
    def _una_sola_prenda(self) -> "TryOnCreate":
        if (self.fabric_trial_id is None) == (self.garment_upload_id is None):
            raise ValueError(
                "Indica la prenda con `fabric_trial_id` o con `garment_upload_id`, "
                "y solo con uno de los dos."
            )
        return self


class TryOnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    person_photo_id: int
    fabric_trial_id: int | None
    garment_upload_id: int | None
    category: GarmentCategory
    status: TrialStatus

    #: La foto de la persona, para enseñar el antes junto al después.
    person_image_url: str | None = None
    #: La prenda exacta que se le mandó al modelo.
    garment_image_url: str | None = None
    output_image_url: str | None = None

    error_message: str | None
    notice: str | None = None
    provider: str | None
    duration_ms: int | None
    #: Qué parte de la foto viene del modelo. El resto es la foto original.
    edited_fraction: float | None = None

    created_at: datetime
    updated_at: datetime
