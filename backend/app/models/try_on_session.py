"""Modelo de sesión de prueba virtual (Virtual Try-On).

En la Etapa 1 esta tabla existe y se puede consultar, pero todavía no se
crean registros: la creación llega cuando se integre el proveedor de IA
(Fase 1 del MVP, tras la autenticación).
"""

import enum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.design import Design
    from app.models.garment import Garment
    from app.models.user import User


class TryOnStatus(str, enum.Enum):
    """Ciclo de vida de una prueba.

    La inferencia de IA es lenta (segundos a minutos) y falla con cierta
    frecuencia. Modelar el estado explícitamente desde el principio evita
    tener que rehacer la tabla cuando se añada el procesamiento en segundo
    plano.
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TryOnSession(Base, TimestampMixin):
    __tablename__ = "try_on_sessions"

    # Fase 2: una prueba puede partir de una prenda del catálogo O de un diseño
    # generado por IA, pero nunca de las dos ni de ninguna. La regla se impone
    # en la base de datos y no solo en Python: los servicios se pueden
    # equivocar, un script suelto puede insertar mal, y una fila con las dos
    # columnas nulas rompería el procesado sin explicación.
    __table_args__ = (
        CheckConstraint(
            "(garment_id IS NOT NULL AND design_id IS NULL) "
            "OR (garment_id IS NULL AND design_id IS NOT NULL)",
            name="ck_try_on_sessions_garment_xor_design",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # RESTRICT y no CASCADE: borrar una prenda no debe destruir el historial
    # del usuario. Para retirar una prenda se usa `active = false`.
    garment_id: Mapped[int | None] = mapped_column(
        ForeignKey("garments.id", ondelete="RESTRICT"), index=True, default=None
    )
    # Origen alternativo: un diseño generado en la Fase 2.
    design_id: Mapped[int | None] = mapped_column(
        ForeignKey("designs.id", ondelete="RESTRICT"), index=True, default=None
    )

    input_image_key: Mapped[str] = mapped_column(String(512), nullable=False)
    # Nulo hasta que la IA devuelve un resultado.
    output_image_key: Mapped[str | None] = mapped_column(String(512), default=None)

    status: Mapped[TryOnStatus] = mapped_column(
        SAEnum(TryOnStatus, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e]),
        default=TryOnStatus.PENDING,
        nullable=False,
        index=True,
    )
    # Diagnóstico cuando status == FAILED.
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    # Qué proveedor de IA generó el resultado ("fashn", "catvton", ...).
    # Permite comparar calidad entre proveedores y reprocesar lo que falló.
    provider: Mapped[str | None] = mapped_column(String(64), default=None)

    user: Mapped["User"] = relationship(back_populates="try_on_sessions")
    garment: Mapped["Garment | None"] = relationship(back_populates="try_on_sessions")
    design: Mapped["Design | None"] = relationship(back_populates="try_on_sessions")

    @property
    def source_image_key(self) -> str | None:
        """Imagen de la prenda que se va a probar, venga de donde venga.

        Evita que cada consumidor tenga que preguntar "¿esto es prenda o
        diseño?" antes de poder trabajar.
        """
        if self.garment is not None:
            return self.garment.image_key
        if self.design is not None:
            return self.design.image_key
        return None

    def __repr__(self) -> str:
        return f"<TryOnSession id={self.id} status={self.status.value}>"
