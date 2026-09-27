"""Modelo de la prueba sobre persona: esta persona, con esta prenda puesta.

DE DÓNDE SALE LA PRENDA
-----------------------
De una de dos cosas que el usuario ya tiene en su taller, nunca de un catálogo
aparte:

- **Una prueba de tela** (`fabric_trial_id`): la prenda con la tela elegida,
  y se usa la IMAGEN QUE YA SE GENERÓ, no una nueva. Es lo que pidió el
  usuario, y es lo coherente: lo que se compró en la comparación es esa
  imagen, y volver a generarla podría cambiar el diseño.
- **Una prenda subida** (`garment_upload_id`): la foto tal cual, con su tela.

Las dos claves van con `SET NULL`: si alguien borra la prueba de tela o la
prenda, la prueba sobre persona se queda —es SU resultado— y conserva la
prenda exacta que se usó en `garment_image_key`. Por eso esa imagen se guarda
aparte y no se deduce: es lo que se le mandó al modelo, y enseñarla junto al
resultado es la única forma de que alguien juzgue si el modelo la respetó.
"""

import enum

from sqlalchemy import Enum as SAEnum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.fabric_trial import TrialStatus


class GarmentCategory(str, enum.Enum):
    """Qué parte del cuerpo cubre la prenda.

    No es una etiqueta de escaparate: decide qué ropa de la foto se sustituye.
    Probar una camisa no debe tocar el pantalón, y probar un vestido sí tiene
    que quitar los dos.
    """

    TOP = "top"
    BOTTOM = "bottom"
    FULL = "full"


class TryOn(Base, TimestampMixin):
    __tablename__ = "try_ons"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_photo_id: Mapped[int] = mapped_column(
        ForeignKey("person_photos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fabric_trial_id: Mapped[int | None] = mapped_column(
        ForeignKey("fabric_trials.id", ondelete="SET NULL"), default=None, index=True
    )
    garment_upload_id: Mapped[int | None] = mapped_column(
        ForeignKey("garment_uploads.id", ondelete="SET NULL"), default=None, index=True
    )

    category: Mapped[GarmentCategory] = mapped_column(
        SAEnum(
            GarmentCategory,
            native_enum=False,
            length=32,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    status: Mapped[TrialStatus] = mapped_column(
        SAEnum(
            TrialStatus,
            native_enum=False,
            length=32,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=TrialStatus.PENDING,
        nullable=False,
        index=True,
    )

    #: La prenda recortada tal como se le mandó al modelo.
    garment_image_key: Mapped[str | None] = mapped_column(String(512), default=None)
    output_image_key: Mapped[str | None] = mapped_column(String(512), default=None)

    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    notice: Mapped[str | None] = mapped_column(Text, default=None)
    provider: Mapped[str | None] = mapped_column(String(64), default=None)
    duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)

    #: Qué parte de la foto viene del modelo, de 0 a 1. El resto son los
    #: píxeles originales de la persona. Es el número que dice cuánto se ha
    #: tocado de la foto, y por eso se guarda con la prueba.
    edited_fraction: Mapped[float | None] = mapped_column(Float, default=None)

    def __repr__(self) -> str:
        return f"<TryOn id={self.id} status={self.status.value} category={self.category.value}>"
