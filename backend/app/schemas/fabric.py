"""Contratos de la API para el catálogo de telas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.fabric import FabricPattern


class FabricCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    reference: str | None = Field(default=None, max_length=64)
    description: str | None = None

    composition: str | None = Field(default=None, max_length=160)
    weight_gsm: int | None = Field(default=None, ge=1, le=2000)
    width_cm: int | None = Field(default=None, ge=10, le=400)
    price_per_meter: float | None = Field(default=None, ge=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)

    color_name: str | None = Field(default=None, max_length=80)
    #: Se valida la forma exacta: un color mal escrito rompe la ficha en el
    #: navegador sin dar ninguna pista de por qué.
    color_hex: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    pattern: FabricPattern = FabricPattern.SOLID

    default_repeat: int = Field(default=6, ge=1, le=40)
    active: bool = True


class FabricUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    reference: str | None = Field(default=None, max_length=64)
    description: str | None = None
    composition: str | None = Field(default=None, max_length=160)
    weight_gsm: int | None = Field(default=None, ge=1, le=2000)
    width_cm: int | None = Field(default=None, ge=10, le=400)
    price_per_meter: float | None = Field(default=None, ge=0)
    color_name: str | None = Field(default=None, max_length=80)
    color_hex: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    pattern: FabricPattern | None = None
    default_repeat: int | None = Field(default=None, ge=1, le=40)
    active: bool | None = None


class FabricRead(BaseModel):
    """Ficha pública de una tela.

    `price_per_meter` sale como número y no como cadena aunque en la base sea
    NUMERIC. Es una decisión consciente: aquí el precio solo se muestra, nunca
    se opera con él, y devolverlo como texto obligaría a cada cliente a
    convertirlo. El día que haya un carrito, ese cálculo se hace en el
    servidor, que es donde la precisión importa.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    reference: str | None
    description: str | None

    composition: str | None
    weight_gsm: int | None
    width_cm: int | None
    price_per_meter: float | None
    currency: str

    color_name: str | None
    color_hex: str | None
    pattern: FabricPattern

    #: Foto de catálogo, para la ficha.
    photo_url: str | None = None
    #: Mosaico que se estampa sobre la prenda. Sin él la tela no se puede probar.
    texture_url: str | None = None
    default_repeat: int
    active: bool
    #: Verdadero si la tela es del taller de quien pregunta (solo él la ve).
    own: bool = False

    created_at: datetime
    updated_at: datetime


# --- Las telas del propio taller (Ep6-Hu7 a Hu11) ---------------------------


class OwnFabricUpdate(BaseModel):
    """Lo que el usuario puede cambiar de una tela suya.

    El mosaico no se edita: sale de la foto. Para otro mosaico, otra foto.
    """

    name: str | None = Field(default=None, min_length=1, max_length=160)
    composition: str | None = Field(default=None, max_length=160)
    description: str | None = None
    default_repeat: int | None = Field(default=None, ge=1, le=40)


class FabricPreview(BaseModel):
    """El mosaico calculado de una foto, ANTES de guardar nada."""

    #: El mosaico en JPEG, como `data:` URL: no se guarda en ningún sitio hasta
    #: que el usuario dice que le sirve.
    mosaic_data_url: str
    color_hex: str
    #: `medir_junta` del mosaico. Por debajo de `seam_limit` no se ve al repetir.
    seam: float
    seam_limit: float
    seam_visible: bool
    #: Lo que tiene mal la foto, con lo que hay que hacer para arreglarlo.
    warnings: list[str]


class OwnFabricCreated(FabricRead):
    """La tela recién guardada, con los avisos de su foto."""

    warnings: list[str] = []
    seam: float | None = None
