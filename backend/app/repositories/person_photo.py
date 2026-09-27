"""Acceso a datos de las fotos de persona."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.person_photo import PersonPhoto


class PersonPhotoRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, photo_id: int) -> PersonPhoto | None:
        return self.session.get(PersonPhoto, photo_id)

    def get_for_user(self, photo_id: int, user_id: int) -> PersonPhoto | None:
        # La pertenencia se comprueba en la consulta, no después: es la foto de
        # alguien, y un `if` olvidado la enseñaría a cualquiera.
        return self.session.execute(
            select(PersonPhoto).where(PersonPhoto.id == photo_id, PersonPhoto.user_id == user_id)
        ).scalar_one_or_none()

    def list_for_user(self, user_id: int) -> list[PersonPhoto]:
        stmt = (
            select(PersonPhoto)
            .where(PersonPhoto.user_id == user_id)
            .order_by(PersonPhoto.created_at.desc(), PersonPhoto.id.desc())
        )
        return list(self.session.execute(stmt).scalars())

    def create(self, **campos) -> PersonPhoto:
        foto = PersonPhoto(**campos)
        self.session.add(foto)
        self.session.commit()
        self.session.refresh(foto)
        return foto

    def delete(self, foto: PersonPhoto) -> None:
        self.session.delete(foto)
        self.session.commit()
