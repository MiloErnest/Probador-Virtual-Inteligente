"""Reglas de negocio de sesiones de prueba virtual.

Etapa 1: solo lectura. La creación de sesiones (subir foto -> llamar al
proveedor de IA -> guardar resultado) es el primer entregable de la Fase 1
del MVP, una vez exista autenticación.
"""

from app.models.try_on_session import TryOnSession
from app.repositories.try_on_session import TryOnSessionRepository
from app.schemas.try_on_session import TryOnSessionRead
from app.services.exceptions import NotFoundError
from app.services.storage import Storage


class TryOnSessionService:
    def __init__(self, repository: TryOnSessionRepository, storage: Storage) -> None:
        self.repository = repository
        self.storage = storage

    def list_by_user(
        self, user_id: int, *, limit: int = 50, offset: int = 0
    ) -> list[TryOnSessionRead]:
        sessions = self.repository.list_by_user(user_id, limit=limit, offset=offset)
        return [self.to_read(session) for session in sessions]

    def get(self, session_id: int) -> TryOnSessionRead:
        session = self.repository.get_by_id(session_id)
        if session is None:
            raise NotFoundError(f"No existe la sesión de prueba {session_id}.")
        return self.to_read(session)

    def to_read(self, session: TryOnSession) -> TryOnSessionRead:
        return TryOnSessionRead(
            id=session.id,
            user_id=session.user_id,
            garment_id=session.garment_id,
            status=session.status,
            input_image_url=self.storage.public_url(session.input_image_key),
            output_image_url=self.storage.public_url(session.output_image_key),
            error_message=session.error_message,
            provider=session.provider,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
