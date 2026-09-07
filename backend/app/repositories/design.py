"""Acceso a datos de diseños generados."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.design import Design, DesignStatus


class DesignRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, design_id: int) -> Design | None:
        return self.session.get(Design, design_id)

    def list_by_user(self, user_id: int, *, limit: int = 50, offset: int = 0) -> list[Design]:
        stmt = (
            select(Design)
            .where(Design.user_id == user_id)
            .order_by(Design.created_at.desc(), Design.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.execute(stmt).scalars())

    def list_completed_by_user(self, user_id: int, *, limit: int = 50) -> list[Design]:
        """Solo los que tienen imagen: son los únicos que se pueden probar."""
        stmt = (
            select(Design)
            .where(
                Design.user_id == user_id,
                Design.status == DesignStatus.COMPLETED,
                Design.image_key.is_not(None),
            )
            .order_by(Design.created_at.desc(), Design.id.desc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars())

    def create(
        self,
        *,
        user_id: int,
        prompt: str,
        parent_id: int | None = None,
        refinement: str | None = None,
    ) -> Design:
        design = Design(
            user_id=user_id,
            prompt=prompt,
            parent_id=parent_id,
            refinement=refinement,
            status=DesignStatus.PENDING,
        )
        self.session.add(design)
        self.session.commit()
        self.session.refresh(design)
        return design

    def save(self, design: Design) -> Design:
        self.session.add(design)
        self.session.commit()
        self.session.refresh(design)
        return design
