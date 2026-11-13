"""Reglas de negocio de usuarios."""

from datetime import UTC, datetime
from urllib.parse import quote

from app.core.config import settings
from app.core.security import (
    VERIFY_EMAIL_EXPIRE_HOURS,
    InvalidTokenError,
    create_email_verification_token,
    decode_email_verification_token,
    hash_password,
)
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate
from app.services.exceptions import (
    ConflictError,
    EmailNotVerifiedError,
    NotFoundError,
    ValidationError,
)


class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def register(self, data: UserCreate) -> User:
        email = data.email.strip().lower()

        if self.repository.get_by_email(email) is not None:
            raise ConflictError("Ya existe una cuenta con ese correo electrónico.")

        return self.repository.create(
            name=data.name.strip(),
            email=email,
            password_hash=hash_password(data.password),
        )

    def get(self, user_id: int) -> User:
        user = self.repository.get_by_id(user_id)
        if user is None:
            raise NotFoundError(f"No existe el usuario {user_id}.")
        return user

    # --- Verificación del correo (Ep5-Hu7) ----------------------------------

    def verification_link(self, user: User) -> str:
        """El enlace del correo. Abre la aplicación web, que lo confirma con la API."""
        token = create_email_verification_token(user.id, user.email)
        return f"{settings.FRONTEND_URL.rstrip('/')}/verificar-correo?token={quote(token)}"

    @staticmethod
    def verification_hours() -> int:
        return VERIFY_EMAIL_EXPIRE_HOURS

    def verify_email(self, token: str) -> User:
        """Marca el correo como verificado. Abrir el enlace dos veces no falla.

        El enlace lleva el correo para el que se emitió: si no coincide con el
        de la cuenta, no vale.
        """
        try:
            user_id, email = decode_email_verification_token(token)
        except InvalidTokenError as exc:
            raise ValidationError("El enlace no es válido o ha caducado. Pide otro desde tu perfil.") from exc

        user = self.repository.get_by_id(user_id)
        if user is None or not user.is_active or user.email != email:
            raise ValidationError("El enlace no es válido o ha caducado. Pide otro desde tu perfil.")

        if user.email_verified_at is None:
            user.email_verified_at = datetime.now(UTC)
            self.repository.save(user)
        return user


def exigir_correo_verificado(user_verified: bool) -> None:
    """La regla de Ep5-Hu7, en un solo sitio: sin correo verificado no hay IA.

    Generar con IA es lo que cuesta dinero, y una cuenta con un correo que no
    existe es la forma barata de saltarse el techo diario: basta con crear
    otra. Probar telas con el motor determinista no se bloquea: es gratis.
    """
    if not user_verified:
        raise EmailNotVerifiedError(
            "Confirma tu correo antes de generar prendas con IA: abre el enlace que te "
            "enviamos al registrarte, o pide otro desde tu perfil."
        )
