"""Acceso a datos de las pruebas de tela."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.fabric_trial import FabricTrial, TrialMethod, TrialStatus


class FabricTrialRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, trial_id: int) -> FabricTrial | None:
        return self.session.get(FabricTrial, trial_id)

    def get_for_user(self, trial_id: int, user_id: int) -> FabricTrial | None:
        return self.session.execute(
            select(FabricTrial).where(
                FabricTrial.id == trial_id, FabricTrial.user_id == user_id
            )
        ).scalar_one_or_none()

    def list_for_user(
        self,
        user_id: int,
        *,
        garment_upload_id: int | None = None,
        limit: int = 60,
        offset: int = 0,
    ) -> list[FabricTrial]:
        stmt = select(FabricTrial).where(FabricTrial.user_id == user_id)
        if garment_upload_id is not None:
            # Filtrar por prenda es lo que sostiene la comparación lado a lado:
            # todas las pruebas de un mismo diseño, juntas.
            stmt = stmt.where(FabricTrial.garment_upload_id == garment_upload_id)

        stmt = (
            stmt.order_by(FabricTrial.created_at.desc(), FabricTrial.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.execute(stmt).scalars())

    def contar_ia_hoy(self, user_id: int) -> int:
        """Pruebas con IA lanzadas por el usuario en las últimas 24 horas.

        Es el techo de gasto dentro de la aplicación. El límite del panel de
        OpenAI protege la cartera; este protege a los demás usuarios de que un
        fallo de uno se coma el presupuesto común.

        Se cuenta una ventana móvil de 24 h y no el día natural: con el día
        natural, alguien que agota el límite a las 23:50 lo tiene entero otra
        vez diez minutos después.
        """
        desde = datetime.now(timezone.utc) - timedelta(hours=24)
        return int(
            self.session.execute(
                select(func.count())
                .select_from(FabricTrial)
                .where(
                    FabricTrial.user_id == user_id,
                    FabricTrial.method == TrialMethod.AI,
                    FabricTrial.created_at >= desde,
                    # Las que fallaron no cuentan: no llegaron a generar imagen
                    # y por tanto no costaron dinero.
                    FabricTrial.status != TrialStatus.FAILED,
                )
            ).scalar_one()
        )

    def create(self, **campos) -> FabricTrial:
        trial = FabricTrial(**campos)
        self.session.add(trial)
        self.session.commit()
        self.session.refresh(trial)
        return trial

    def save(self, trial: FabricTrial) -> FabricTrial:
        self.session.add(trial)
        self.session.commit()
        self.session.refresh(trial)
        return trial

    def delete(self, trial: FabricTrial) -> None:
        self.session.delete(trial)
        self.session.commit()
