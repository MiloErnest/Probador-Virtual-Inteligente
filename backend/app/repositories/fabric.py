"""Acceso a datos del catálogo de telas."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.fabric import Fabric, FabricPattern


class FabricRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, fabric_id: int) -> Fabric | None:
        return self.session.get(Fabric, fabric_id)

    def get_by_name(self, name: str) -> Fabric | None:
        return self.session.execute(
            select(Fabric).where(Fabric.name == name)
        ).scalar_one_or_none()

    def list(
        self,
        *,
        pattern: FabricPattern | None = None,
        only_active: bool = True,
        only_probable: bool = False,
        limit: int = 60,
        offset: int = 0,
    ) -> list[Fabric]:
        stmt = select(Fabric)
        if only_active:
            stmt = stmt.where(Fabric.active.is_(True))
        if pattern is not None:
            stmt = stmt.where(Fabric.pattern == pattern)
        if only_probable:
            # Sin mosaico no se puede estampar sobre nada. El probador pide
            # esto para no ofrecer telas que van a fallar al elegirlas.
            stmt = stmt.where(Fabric.texture_key.is_not(None))

        stmt = stmt.order_by(Fabric.name.asc(), Fabric.id.asc()).limit(limit).offset(offset)
        return list(self.session.execute(stmt).scalars())

    def create(self, **campos) -> Fabric:
        fabric = Fabric(**campos)
        self.session.add(fabric)
        self.session.commit()
        self.session.refresh(fabric)
        return fabric

    def save(self, fabric: Fabric) -> Fabric:
        self.session.add(fabric)
        self.session.commit()
        self.session.refresh(fabric)
        return fabric
