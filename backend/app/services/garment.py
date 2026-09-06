"""Reglas de negocio de prendas.

Este servicio es también el punto donde `image_key` (interno) se traduce a
`image_url` (público), para que ni las rutas ni el frontend sepan cómo se
almacenan los archivos.
"""

from app.models.garment import Garment, GarmentCategory
from app.repositories.garment import GarmentRepository
from app.schemas.garment import GarmentCreate, GarmentRead
from app.services.exceptions import NotFoundError, ValidationError
from app.services.storage import ALLOWED_IMAGE_TYPES, FOLDER_GARMENTS, Storage


class GarmentService:
    def __init__(self, repository: GarmentRepository, storage: Storage) -> None:
        self.repository = repository
        self.storage = storage

    # --- Consultas ---

    def list(
        self,
        *,
        category: GarmentCategory | None = None,
        include_inactive: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[GarmentRead]:
        garments = self.repository.list(
            category=category,
            only_active=not include_inactive,
            limit=limit,
            offset=offset,
        )
        return [self.to_read(garment) for garment in garments]

    def get(self, garment_id: int) -> GarmentRead:
        return self.to_read(self._get_or_fail(garment_id))

    # --- Comandos ---

    def create(self, data: GarmentCreate) -> GarmentRead:
        garment = self.repository.create(
            name=data.name.strip(),
            description=data.description,
            category=data.category,
            active=data.active,
        )
        return self.to_read(garment)

    def set_image(
        self, garment_id: int, *, content: bytes, content_type: str | None, max_bytes: int
    ) -> GarmentRead:
        garment = self._get_or_fail(garment_id)

        extension = ALLOWED_IMAGE_TYPES.get(content_type or "")
        if extension is None:
            permitidos = ", ".join(sorted(ALLOWED_IMAGE_TYPES))
            raise ValidationError(
                f"Tipo de archivo no permitido ({content_type!r}). Se aceptan: {permitidos}."
            )
        if not content:
            raise ValidationError("El archivo está vacío.")
        if len(content) > max_bytes:
            raise ValidationError(
                f"La imagen supera el tamaño máximo de {max_bytes // (1024 * 1024)} MB."
            )

        previous_key = garment.image_key
        garment.image_key = self.storage.save(
            content, folder=FOLDER_GARMENTS, extension=extension
        )
        self.repository.save(garment)

        # Se borra la anterior solo tras persistir la nueva, para no dejar la
        # prenda sin imagen si la escritura en base de datos falla.
        if previous_key:
            self.storage.delete(previous_key)

        return self.to_read(garment)

    # --- Traducción modelo -> contrato público ---

    def to_read(self, garment: Garment) -> GarmentRead:
        return GarmentRead(
            id=garment.id,
            name=garment.name,
            description=garment.description,
            category=garment.category,
            active=garment.active,
            image_url=self.storage.public_url(garment.image_key),
            created_at=garment.created_at,
            updated_at=garment.updated_at,
        )

    def _get_or_fail(self, garment_id: int) -> Garment:
        garment = self.repository.get_by_id(garment_id)
        if garment is None:
            raise NotFoundError(f"No existe la prenda {garment_id}.")
        return garment
