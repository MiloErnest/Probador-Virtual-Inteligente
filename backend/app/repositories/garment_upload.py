"""Acceso a datos de las prendas subidas por el usuario."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.garment_upload import GarmentUpload


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
