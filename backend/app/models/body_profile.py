"""Perfil corporal del usuario (Fase 3).

UNO POR USUARIO
---------------
`user_id` es único. Un usuario tiene un cuerpo; guardar un historial de
perfiles complicaría cada consulta ("¿cuál es el vigente?") sin resolver
ningún problema real. Si algún día hace falta seguir la evolución, se añade
una tabla de mediciones aparte y esta se queda como "el perfil actual".

MEDIDAS OPCIONALES
------------------
Todas las medidas admiten nulo a propósito. Un usuario puede escribir solo su
altura, o dejar que el análisis por foto rellene el resto. Exigirlas todas de
golpe sería un formulario que nadie termina, y la recomendación de talla ya
sabe trabajar con lo que haya.

Las medidas se guardan en CENTÍMETROS, siempre. La conversión a otras
unidades, si algún día hace falta, es cosa de la interfaz.
"""

import enum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum as SAEnum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class MeasurementSource(str, enum.Enum):
    """De dónde salieron las medidas. Cambia cuánto hay que fiarse de ellas."""

    MANUAL = "manual"      # las escribió el usuario
    ANALYSIS = "analysis"  # las estimó el análisis de la fotografía


class BodyProfile(Base, TimestampMixin):
    __tablename__ = "body_profiles"

    # Rangos amplios a propósito: no son medidas "normales", son el límite de
    # lo físicamente posible. Sirven para atrapar erratas evidentes (una
    # altura de 17 cm, un pecho de 900) sin juzgar a nadie por su cuerpo.
    __table_args__ = (
        CheckConstraint("height_cm IS NULL OR (height_cm BETWEEN 50 AND 260)",
                        name="ck_body_profiles_height_range"),
        CheckConstraint("weight_kg IS NULL OR (weight_kg BETWEEN 20 AND 400)",
                        name="ck_body_profiles_weight_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    height_cm: Mapped[float | None] = mapped_column(Float, default=None)
    weight_kg: Mapped[float | None] = mapped_column(Float, default=None)

    # Las cuatro medidas que usan las tablas de tallaje de ropa.
    chest_cm: Mapped[float | None] = mapped_column(Float, default=None)
    waist_cm: Mapped[float | None] = mapped_column(Float, default=None)
    hips_cm: Mapped[float | None] = mapped_column(Float, default=None)
    inseam_cm: Mapped[float | None] = mapped_column(Float, default=None)

    source: Mapped[MeasurementSource] = mapped_column(
        SAEnum(MeasurementSource, native_enum=False, length=32,
               values_callable=lambda e: [m.value for m in e]),
        default=MeasurementSource.MANUAL,
        nullable=False,
    )

    # Foto usada en el último análisis. Nulo si las medidas son manuales.
    # Se guarda la clave, no la imagen: es una fotografía del cuerpo del
    # usuario y merece el mismo trato que el resto de archivos privados.
    photo_key: Mapped[str | None] = mapped_column(String(512), default=None)

    user: Mapped["User"] = relationship(back_populates="body_profile")

    def __repr__(self) -> str:
        return f"<BodyProfile user_id={self.user_id} source={self.source.value}>"
