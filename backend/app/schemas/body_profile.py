"""Contratos de la API para el perfil corporal y la talla (Fase 3)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.body_profile import MeasurementSource
from app.models.garment import GarmentCategory

# Rangos de cordura, los mismos que las CHECK de la tabla. Se repiten aquí
# para que el error llegue como un 422 explicando qué campo está mal, y no
# como un error de base de datos que no le dice nada al usuario.
HEIGHT = Field(None, ge=50, le=260, description="Altura en centímetros")
WEIGHT = Field(None, ge=20, le=400, description="Peso en kilogramos")
GIRTH = Field(None, ge=20, le=250, description="Contorno en centímetros")
LENGTH = Field(None, ge=20, le=150, description="Longitud en centímetros")


class BodyProfileUpdate(BaseModel):
    """Actualización parcial: solo se tocan los campos que llegan.

    Todos son opcionales a propósito. Un usuario puede escribir solo su
    altura; exigirlas todas de golpe sería un formulario que nadie termina.
    """

    height_cm: float | None = HEIGHT
    weight_kg: float | None = WEIGHT
    chest_cm: float | None = GIRTH
    waist_cm: float | None = GIRTH
    hips_cm: float | None = GIRTH
    inseam_cm: float | None = LENGTH


class BodyProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    height_cm: float | None = None
    weight_kg: float | None = None
    chest_cm: float | None = None
    waist_cm: float | None = None
    hips_cm: float | None = None
    inseam_cm: float | None = None
    source: MeasurementSource
    photo_url: str | None = None
    # Solo viene tras un análisis. Es lo que permite a la interfaz avisar de
    # que las medidas son una estimación y no una medición.
    analysis_confidence: float | None = None
    created_at: datetime
    updated_at: datetime


class SizeRecommendationRead(BaseModel):
    """Recomendación de talla, con el porqué.

    `reason` y `per_measurement` no sobran: una recomendación que no se puede
    cuestionar es una que nadie se cree. Si el usuario ve que salió de su
    cintura, entiende por qué le sale L cuando suele usar M.
    """

    # Nulo cuando faltan las medidas necesarias. `reason` explica cuáles.
    size: str | None
    category: GarmentCategory
    based_on: list[str]
    reason: str
    per_measurement: dict[str, str]
    confidence: float
