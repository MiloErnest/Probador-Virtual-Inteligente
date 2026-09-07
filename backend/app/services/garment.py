"""Reglas de negocio de prendas.

Este servicio es también el punto donde `image_key` (interno) se traduce a
`image_url` (público), para que ni las rutas ni el frontend sepan cómo se
almacenan los archivos.
"""

from app.models.garment import Garment, GarmentCategory
from app.repositories.garment import GarmentRepository
from app.schemas.garment import GarmentCreate, GarmentRead
from app.services.exceptions import NotFoundError
from app.services.images import validate_image
from app.services.storage import FOLDER_GARMENTS, Storage


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

    def set_image(self, garment_id: int, *, content: bytes, max_bytes: int) -> GarmentRead:
        garment = self._get_or_fail(garment_id)

        # Fase 1: la validación pasó a mirar el CONTENIDO del archivo en vez
        # de la cabecera `Content-Type`, que la escribe quien sube el archivo
        # y por tanto no prueba nada. Ver app/services/images.py.
        extension = validate_image(content, max_bytes=max_bytes)

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
