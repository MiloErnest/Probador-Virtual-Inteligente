"""Modelo de prenda del catálogo."""

import enum

from sqlalchemy import Boolean, Enum as SAEnum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class GarmentCategory(str, enum.Enum):
    """Categorías del catálogo.

    Se persiste como VARCHAR (`native_enum=False`) en vez de un ENUM nativo de
    PostgreSQL: añadir un valor nuevo a un ENUM nativo requiere una migración
    `ALTER TYPE`, y esta lista va a crecer.

    La categoría no es solo una etiqueta de escaparate: el probador la usa
    para decidir DÓNDE se ancla la prenda sobre el cuerpo. Una camiseta cuelga
    de los hombros; un pantalón, de las caderas. Ver `frontend/src/ar/fit.ts`.
    """

    DRESS = "dress"
    TOP = "top"
    BOTTOM = "bottom"
    OUTERWEAR = "outerwear"
    OTHER = "other"


class GarmentFabric(str, enum.Enum):
    """Tejido de la prenda.

    Hoy es solo un dato del catálogo con un efecto pequeño y honesto: el
    probador lo usa para decidir cuánto se ciñe la prenda al contorno del
    cuerpo. Un cuero mantiene su forma; un punto se pega. No es una simulación
    de tela —eso es Fase 4, con materiales PBR y caída real—, pero el dato ya
    vive donde tiene que vivir, así que esa fase no obliga a migrar nada.

    Nullable a propósito: una prenda del catálogo puede no tener el tejido
    registrado, y forzar un valor por defecto sería inventarse el dato.
    """

    COTTON = "cotton"
    LINEN = "linen"
    SILK = "silk"
    WOOL = "wool"
    KNIT = "knit"
    DENIM = "denim"
    LEATHER = "leather"
    SYNTHETIC = "synthetic"


class Garment(Base, TimestampMixin):
    __tablename__ = "garments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    category: Mapped[GarmentCategory] = mapped_column(
        SAEnum(
            GarmentCategory,
            native_enum=False,
            length=32,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=GarmentCategory.OTHER,
        nullable=False,
        index=True,
    )
    fabric: Mapped[GarmentFabric | None] = mapped_column(
        SAEnum(
            GarmentFabric,
            native_enum=False,
            length=32,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=None,
    )

    # Se guarda la CLAVE del archivo en el almacén (p. ej. "garments/ab12.jpg"),
    # no una URL completa. La URL pública se deriva en la capa de servicio, de
    # modo que migrar de disco local a S3/R2 no obliga a reescribir datos.
    image_key: Mapped[str | None] = mapped_column(String(512), default=None)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<Garment id={self.id} name={self.name!r}>"
