"""Diseño de prenda generado a partir de una descripción en texto (Fase 2).

Comparte ciclo de vida con `TryOnSession` (`pending -> processing ->
completed | failed`) porque el problema es el mismo: una generación lenta que
puede fallar y que no se puede resolver dentro de una petición HTTP.

ITERACIÓN
---------
`parent_id` apunta al diseño del que se partió. Un diseño editado NO
sobrescribe al anterior: crea uno nuevo que lo referencia. Así queda el rastro
completo de cómo se llegó al resultado, que en un proceso creativo es la mitad
del valor, y nunca se pierde una versión que gustaba más.
"""

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.try_on_session import TryOnSession
    from app.models.user import User


class DesignStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Design(Base, TimestampMixin):
    __tablename__ = "designs"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # Descripción que escribió el usuario. Se guarda literal para poder
    # reproducir la generación y para mostrarla en el historial.
    prompt: Mapped[str] = mapped_column(Text, nullable=False)

    # Instrucción de la iteración ("hazlo más largo", "en azul"). Nulo en el
    # primer diseño de una cadena.
    refinement: Mapped[str | None] = mapped_column(Text, default=None)

    # RESTRICT y no CASCADE: borrar un diseño no debe llevarse por delante las
    # iteraciones que salieron de él.
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("designs.id", ondelete="RESTRICT"), index=True, default=None
    )

    image_key: Mapped[str | None] = mapped_column(String(512), default=None)

    status: Mapped[DesignStatus] = mapped_column(
        SAEnum(DesignStatus, native_enum=False, length=32,
               values_callable=lambda e: [m.value for m in e]),
        default=DesignStatus.PENDING,
        nullable=False,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    provider: Mapped[str | None] = mapped_column(String(64), default=None)

    user: Mapped["User"] = relationship(back_populates="designs")
    parent: Mapped["Design | None"] = relationship(remote_side="Design.id", back_populates="children")
    children: Mapped[list["Design"]] = relationship(back_populates="parent")
    try_on_sessions: Mapped[list["TryOnSession"]] = relationship(back_populates="design")

    def __repr__(self) -> str:
        return f"<Design id={self.id} status={self.status.value}>"
