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

    def get_for_user(self, session_id: int, *, user_id: int) -> TryOnSessionRead:
        """Devuelve una prueba solo si pertenece a ese usuario.

        Una prueba ajena produce el mismo `NotFoundError` que una inexistente,
        y con el mismo mensaje. Es deliberado: si el error distinguiera ambos
        casos, recorrer identificadores permitiría contar cuántas pruebas hay
        en el sistema y quién las tiene.

        La comprobación vive aquí y no en la ruta porque "de quién es este
        recurso" es una regla de negocio. La ruta solo traduce el error a un
        404.
        """
        session = self.repository.get_by_id(session_id)
        if session is None or session.user_id != user_id:
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
