"""Acceso a datos de las prendas subidas por el usuario."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.garment_upload import GarmentKind, GarmentStatus, GarmentUpload


class GarmentUploadRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, upload_id: int) -> GarmentUpload | None:
        return self.session.get(GarmentUpload, upload_id)

    def get_for_user(self, upload_id: int, user_id: int) -> GarmentUpload | None:
        """La prenda, SOLO si es de ese usuario.

        El filtro por usuario va en la consulta y no en un `if` posterior. Es
        la misma regla que ya costó un agujero en este proyecto: el historial
        aceptaba `?user_id=` y bastaba cambiar un número para leer el de
        cualquiera. Si la pertenencia se comprueba en la base, no hay forma de
        olvidarse de comprobarla.
        """
        return self.session.execute(
            select(GarmentUpload).where(
                GarmentUpload.id == upload_id, GarmentUpload.user_id == user_id
            )
        ).scalar_one_or_none()

    def list_for_user(self, user_id: int, *, limit: int = 60, offset: int = 0):
        stmt = (
            select(GarmentUpload)
            .where(GarmentUpload.user_id == user_id)
            .order_by(GarmentUpload.created_at.desc(), GarmentUpload.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.execute(stmt).scalars())

    def claves_de_sus_pruebas(self, upload_id: int) -> list[str]:
        """Las imágenes de las pruebas de tela de una prenda.

        La base borra esas pruebas en cascada con la prenda, pero sus archivos
        no: sin esto, cada prenda borrada dejaba sus resultados huérfanos en
        el almacén.
        """
        from app.models.fabric_trial import FabricTrial

        return [
            clave
            for clave in self.session.execute(
                select(FabricTrial.output_image_key).where(
                    FabricTrial.garment_upload_id == upload_id
                )
            ).scalars()
            if clave
        ]

    def tiene_pruebas(self, upload_id: int) -> bool:
        from app.models.fabric_trial import FabricTrial

        return (
            self.session.execute(
                select(FabricTrial.id).where(FabricTrial.garment_upload_id == upload_id).limit(1)
            ).first()
            is not None
        )

    def contar_bocetos_generados_hoy(self, user_id: int) -> int:
        """Prendas generadas con IA a partir de un boceto en las últimas 24 horas.

        Cuenta para el mismo techo de gasto que las pruebas con IA
        (`FabricTrialRepository.contar_ia_hoy`), y con la misma ventana móvil.
        Las que fallaron no cuentan: casi siempre fallan antes de generar.
        """
        desde = datetime.now(timezone.utc) - timedelta(hours=24)
        return int(
            self.session.execute(
                select(func.count())
                .select_from(GarmentUpload)
                .where(
                    GarmentUpload.user_id == user_id,
                    GarmentUpload.kind == GarmentKind.SKETCH,
                    GarmentUpload.created_at >= desde,
                    GarmentUpload.status != GarmentStatus.FAILED,
                )
            ).scalar_one()
        )

    def create(self, **campos) -> GarmentUpload:
        upload = GarmentUpload(**campos)
        self.session.add(upload)
        self.session.commit()
        self.session.refresh(upload)
        return upload

    def save(self, upload: GarmentUpload) -> GarmentUpload:
        self.session.add(upload)
        self.session.commit()
        self.session.refresh(upload)
        return upload

    def delete(self, upload: GarmentUpload) -> None:
        self.session.delete(upload)
        self.session.commit()
