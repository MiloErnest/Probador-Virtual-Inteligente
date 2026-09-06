"""Reglas de negocio de la autenticación.

Como el resto de servicios, este no conoce FastAPI: lanza errores de dominio
y es la capa de rutas la que decide qué código HTTP les corresponde. Así el
mismo servicio sirve desde un script o un worker sin arrastrar el framework.
"""

from app.core.security import (
    DUMMY_PASSWORD_HASH,
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    verify_password,
)
from app.models.user import User
from app.repositories.user import UserRepository
from app.services.exceptions import AuthenticationError


class AuthService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def authenticate(self, email: str, password: str) -> User:
        """Comprueba las credenciales y devuelve el usuario.

        Lanza `AuthenticationError` —siempre el mismo— si el email no existe,
        si la contraseña no coincide o si la cuenta está desactivada.
        """
        user = self.repository.get_by_email(email.strip().lower())

        if user is None:
            # Se verifica igualmente contra un hash señuelo. Sin esto, un
            # email inexistente respondería mucho más rápido que uno real
            # (bcrypt es lento a propósito), y esa diferencia de tiempo
            # bastaría para averiguar qué correos están registrados.
            verify_password(password, DUMMY_PASSWORD_HASH)
            raise AuthenticationError("Correo electrónico o contraseña incorrectos.")

        if not verify_password(password, user.password_hash):
            raise AuthenticationError("Correo electrónico o contraseña incorrectos.")

        if not user.is_active:
            raise AuthenticationError("Correo electrónico o contraseña incorrectos.")

        return user

    def issue_token(self, user: User) -> tuple[str, int]:
        """Emite el token de acceso de un usuario ya autenticado."""
        return create_access_token(user.id)

    def resolve_token(self, token: str) -> User:
        """Traduce un token en el usuario que representa.

        Se vuelve a leer el usuario de la base en cada petición en lugar de
        confiar en lo que diga el token. Es una consulta por clave primaria, y
        a cambio una cuenta desactivada deja de tener acceso en el momento, sin
        esperar a que caduque su token.
        """
        try:
            user_id = decode_access_token(token)
        except InvalidTokenError as exc:
            raise AuthenticationError("Token inválido o caducado.") from exc

        user = self.repository.get_by_id(user_id)

        # El usuario pudo borrarse o desactivarse después de emitir el token.
        if user is None or not user.is_active:
            raise AuthenticationError("Token inválido o caducado.")

        return user
