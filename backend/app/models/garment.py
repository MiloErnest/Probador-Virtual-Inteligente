"""Modelo de prenda del catálogo."""

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum as SAEnum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.try_on_session import TryOnSession


class GarmentCategory(str, enum.Enum):
    """Categorías del catálogo.

    Se persiste como VARCHAR con CHECK constraint (`native_enum=False`) en vez
    de un ENUM nativo de PostgreSQL: añadir un valor nuevo a un ENUM nativo
    requiere una migración `ALTER TYPE`, y esta lista va a crecer.
    """

    DRESS = "dress"
    TOP = "top"
    BOTTOM = "bottom"
    OUTERWEAR = "outerwear"
    OTHER = "other"


class Garment(Base, TimestampMixin):
    __tablename__ = "garments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    category: Mapped[GarmentCategory] = mapped_column(
        SAEnum(GarmentCategory, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e]),
        default=GarmentCategory.OTHER,
        nullable=False,
        index=True,
    )

    # Se guarda la CLAVE del archivo en el almacén (p. ej. "garments/ab12.jpg"),
    # no una URL completa. La URL pública se deriva en la capa de servicio, de
    # modo que migrar de disco local a S3/R2 no obliga a reescribir datos.
    image_key: Mapped[str | None] = mapped_column(String(512), default=None)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    try_on_sessions: Mapped[list["TryOnSession"]] = relationship(back_populates="garment")

    def __repr__(self) -> str:
        return f"<Garment id={self.id} name={self.name!r}>"
