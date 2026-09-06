"""Reglas de negocio de usuarios."""

from app.core.security import hash_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate
from app.services.exceptions import ConflictError, NotFoundError


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
