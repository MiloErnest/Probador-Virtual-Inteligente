"""Endpoints del catálogo de prendas.

La creación de la prenda (JSON) y la subida de su imagen (multipart) están
separadas a propósito: mezclar ambas en un solo endpoint obliga a enviar
todos los campos como `Form(...)`, lo que impide validar con un schema
Pydantic y complica los tests.
"""

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app.api.deps import GarmentServiceDep
from app.core.config import settings
from app.models.garment import GarmentCategory
from app.schemas.garment import GarmentCreate, GarmentRead
from app.services.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/garments", tags=["garments"])


@router.get("", response_model=list[GarmentRead], summary="Listar prendas del catálogo")
def list_garments(
    service: GarmentServiceDep,
    category: GarmentCategory | None = Query(None, description="Filtrar por categoría"),
    include_inactive: bool = Query(False, description="Incluir prendas retiradas"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[GarmentRead]:
    return service.list(
        category=category,
        include_inactive=include_inactive,
        limit=limit,
        offset=offset,
    )


@router.get("/{garment_id}", response_model=GarmentRead, summary="Obtener una prenda")
def get_garment(garment_id: int, service: GarmentServiceDep) -> GarmentRead:
    try:
        return service.get(garment_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post(
    "",
    response_model=GarmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una prenda",
)
def create_garment(payload: GarmentCreate, service: GarmentServiceDep) -> GarmentRead:
    return service.create(payload)


@router.post(
    "/{garment_id}/image",
    response_model=GarmentRead,
    summary="Subir o reemplazar la imagen de una prenda",
)
async def upload_garment_image(
    garment_id: int,
    service: GarmentServiceDep,
    file: UploadFile = File(..., description="JPEG, PNG o WebP"),
) -> GarmentRead:
    content = await file.read()
    try:
        return service.set_image(
            garment_id,
            content=content,
            content_type=file.content_type,
            max_bytes=settings.max_upload_bytes,
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
