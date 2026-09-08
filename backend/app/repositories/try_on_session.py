"""Acceso a datos de sesiones de prueba virtual."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.try_on_session import TryOnSession, TryOnStatus


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

    def create(
        self,
        *,
        user_id: int,
        input_image_key: str,
        garment_id: int | None = None,
        design_id: int | None = None,
    ) -> TryOnSession:
        session = TryOnSession(
            user_id=user_id,
            garment_id=garment_id,
            design_id=design_id,
            input_image_key=input_image_key,
            status=TryOnStatus.PENDING,
        )
        self.session.add(session)
        self.session.commit()
        self.session.refresh(session)
        return session

    def delete(self, session: TryOnSession) -> None:
        self.session.delete(session)
        self.session.commit()

    def save(self, session: TryOnSession) -> TryOnSession:
        self.session.add(session)
        self.session.commit()
        self.session.refresh(session)
        return session
