"""Contratos de entrada/salida de la API para prendas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.garment import GarmentCategory, GarmentFabric


class GarmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    category: GarmentCategory = GarmentCategory.OTHER
    fabric: GarmentFabric | None = None
    active: bool = True


class GarmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    category: GarmentCategory | None = None
    fabric: GarmentFabric | None = None
    active: bool | None = None


class GarmentRead(BaseModel):
    """Salida de la API.

    Expone `image_url` (URL pública, lista para usar en un <img>) aunque en la
    base de datos se guarde `image_key`. El cliente no necesita saber dónde
    vive físicamente el archivo.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    category: GarmentCategory
    fabric: GarmentFabric | None = None
    active: bool
    image_url: str | None = None
    created_at: datetime
    updated_at: datetime
