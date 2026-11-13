"""Modelo de usuario."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Permite desactivar una cuenta sin borrarla.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Cuándo se comprobó que el buzón existe (Ep5-Hu7). Vacío: sin verificar, y
    # sin poder generar prendas con IA, que es lo que cuesta dinero. Una fecha
    # y no un booleano: dice además cuándo, y una cuenta que llegue verificada
    # de otro sitio (Google, cuando exista) se marca al crearla.
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
