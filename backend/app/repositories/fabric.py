"""Acceso a datos de las telas: el catálogo y las de cada taller.

Una tela con `owner_id` vacío es del catálogo; con valor, de ese usuario. Las
consultas del catálogo filtran SIEMPRE por `owner_id IS NULL`: si no, la tela
que alguien fotografió en su taller aparecería en el escaparate público.
"""

# Sin esto, `list[Fabric]` en un método escrito DESPUÉS de `def list` se
# refiere a ese método y no al tipo, y la clase no llega a importarse.
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.fabric import Fabric, FabricPattern
from app.models.fabric_trial import FabricTrial


class FabricRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, fabric_id: int) -> Fabric | None:
        """Cualquier tela, sea de quien sea. Para quien ya sabe que puede verla."""
        return self.session.get(Fabric, fabric_id)

    def get_catalog(self, fabric_id: int) -> Fabric | None:
        """Una tela del catálogo. Una tela de un taller responde como si no existiera."""
        tela = self.session.get(Fabric, fabric_id)
        return tela if tela is not None and tela.owner_id is None else None

    def get_for_owner(self, fabric_id: int, owner_id: int) -> Fabric | None:
        tela = self.session.get(Fabric, fabric_id)
        return tela if tela is not None and tela.owner_id == owner_id else None

    def get_visible(self, fabric_id: int, user_id: int) -> Fabric | None:
        """Una tela con la que este usuario puede probar: del catálogo o suya."""
        tela = self.session.get(Fabric, fabric_id)
        if tela is None or tela.owner_id not in (None, user_id):
            return None
        return tela

    def get_by_name(self, name: str) -> Fabric | None:
        """Una tela del catálogo por su nombre."""
        return self.session.execute(
            select(Fabric).where(Fabric.name == name, Fabric.owner_id.is_(None))
        ).scalar_one_or_none()

    def get_by_name_for_owner(self, name: str, owner_id: int) -> Fabric | None:
        """Una tela ACTIVA de este usuario por su nombre.

        Las retiradas no cuentan: si borró «Lino crudo» y vuelve a subirla, no
        tiene sentido decirle que ya la tiene.
        """
        return self.session.execute(
            select(Fabric).where(
                Fabric.name == name,
                Fabric.owner_id == owner_id,
                Fabric.active.is_(True),
            )
        ).scalars().first()

    def list(
        self,
        *,
        pattern: FabricPattern | None = None,
        only_active: bool = True,
        only_probable: bool = False,
        limit: int = 60,
        offset: int = 0,
    ) -> list[Fabric]:
        """El catálogo de la tienda. Nunca incluye las telas de los talleres."""
        stmt = select(Fabric).where(Fabric.owner_id.is_(None))
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

    def list_for_owner(self, owner_id: int, *, include_retired: bool = False) -> list[Fabric]:
        """Las telas de un taller, las más nuevas primero.

        `include_retired` sirve al historial: una prueba hecha con una tela que
        después se borró sigue necesitando su nombre.
        """
        stmt = select(Fabric).where(Fabric.owner_id == owner_id)
        if not include_retired:
            stmt = stmt.where(Fabric.active.is_(True))
        stmt = stmt.order_by(Fabric.created_at.desc(), Fabric.id.desc())
        return list(self.session.execute(stmt).scalars())

    def count_trials(self, fabric_id: int) -> int:
        return int(
            self.session.execute(
                select(func.count()).select_from(FabricTrial).where(FabricTrial.fabric_id == fabric_id)
            ).scalar_one()
        )

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

    def delete(self, fabric: Fabric) -> None:
        self.session.delete(fabric)
        self.session.commit()
