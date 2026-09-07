"""Acceso a datos del perfil corporal."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.body_profile import BodyProfile


class BodyProfileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_user(self, user_id: int) -> BodyProfile | None:
        stmt = select(BodyProfile).where(BodyProfile.user_id == user_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def create(self, *, user_id: int) -> BodyProfile:
        perfil = BodyProfile(user_id=user_id)
        self.session.add(perfil)
        self.session.commit()
        self.session.refresh(perfil)
        return perfil

    def save(self, perfil: BodyProfile) -> BodyProfile:
        self.session.add(perfil)
        self.session.commit()
        self.session.refresh(perfil)
        return perfil

    def delete(self, perfil: BodyProfile) -> None:
        self.session.delete(perfil)
        self.session.commit()
