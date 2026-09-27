"""Acceso a datos de las pruebas sobre persona."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.try_on import TryOn


class TryOnRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, try_on_id: int) -> TryOn | None:
        return self.session.get(TryOn, try_on_id)

    def get_for_user(self, try_on_id: int, user_id: int) -> TryOn | None:
        return self.session.execute(
            select(TryOn).where(TryOn.id == try_on_id, TryOn.user_id == user_id)
        ).scalar_one_or_none()

    def list_for_user(
        self,
        user_id: int,
        *,
        person_photo_id: int | None = None,
        limit: int = 60,
        offset: int = 0,
    ) -> list[TryOn]:
        stmt = select(TryOn).where(TryOn.user_id == user_id)
        if person_photo_id is not None:
            stmt = stmt.where(TryOn.person_photo_id == person_photo_id)
        stmt = stmt.order_by(TryOn.created_at.desc(), TryOn.id.desc()).limit(limit).offset(offset)
        return list(self.session.execute(stmt).scalars())

    def list_for_photo(self, person_photo_id: int) -> list[TryOn]:
        """Todas las pruebas hechas sobre una foto, para borrar sus archivos."""
        return list(
            self.session.execute(
                select(TryOn).where(TryOn.person_photo_id == person_photo_id)
            ).scalars()
        )

    def create(self, **campos) -> TryOn:
        prueba = TryOn(**campos)
        self.session.add(prueba)
        self.session.commit()
        self.session.refresh(prueba)
        return prueba

    def save(self, prueba: TryOn) -> TryOn:
        self.session.add(prueba)
        self.session.commit()
        self.session.refresh(prueba)
        return prueba

    def delete(self, prueba: TryOn) -> None:
        self.session.delete(prueba)
        self.session.commit()
