"""Acceso a datos de prendas."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.garment import Garment, GarmentCategory


class GarmentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, garment_id: int) -> Garment | None:
        return self.session.get(Garment, garment_id)

    def list(
        self,
        *,
        category: GarmentCategory | None = None,
        only_active: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Garment]:
        stmt = select(Garment)
        if only_active:
            stmt = stmt.where(Garment.active.is_(True))
        if category is not None:
            stmt = stmt.where(Garment.category == category)
        stmt = stmt.order_by(Garment.created_at.desc(), Garment.id.desc())
        stmt = stmt.limit(limit).offset(offset)
        return list(self.session.execute(stmt).scalars())

    def create(
        self,
        *,
        name: str,
        description: str | None,
        category: GarmentCategory,
        active: bool,
    ) -> Garment:
        garment = Garment(
            name=name,
            description=description,
            category=category,
            active=active,
        )
        self.session.add(garment)
        self.session.commit()
        self.session.refresh(garment)
        return garment

    def save(self, garment: Garment) -> Garment:
        """Persiste cambios sobre una instancia ya gestionada por la sesión."""
        self.session.add(garment)
        self.session.commit()
        self.session.refresh(garment)
        return garment
