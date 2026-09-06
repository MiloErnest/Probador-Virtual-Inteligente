"""Acceso a datos de sesiones de prueba virtual (solo lectura en Etapa 1)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.try_on_session import TryOnSession


class TryOnSessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, session_id: int) -> TryOnSession | None:
        return self.session.get(TryOnSession, session_id)

    def list_by_user(
        self, user_id: int, *, limit: int = 50, offset: int = 0
    ) -> list[TryOnSession]:
        stmt = (
            select(TryOnSession)
            .where(TryOnSession.user_id == user_id)
            .order_by(TryOnSession.created_at.desc(), TryOnSession.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.execute(stmt).scalars())
