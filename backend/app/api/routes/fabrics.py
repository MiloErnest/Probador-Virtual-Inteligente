"""Endpoints del catálogo de telas.

Reparto de acceso, igual que en el resto del proyecto:
  - Leer el catálogo es PÚBLICO. Es el escaparate de la tienda textil.
  - Dar de alta una tela y subirle imágenes exige token.

Limitación conocida y aceptada: cualquier usuario registrado puede dar de alta
telas, porque no existe la distinción usuario/administrador. Añadir un rol
ahora sería infraestructura por adelantado (regla 11); llegará cuando haya un
panel de administración que la necesite.
"""

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app.api.deps import CurrentUserDep, FabricServiceDep
from app.core.config import settings
from app.models.fabric import FabricPattern
from app.schemas.fabric import FabricCreate, FabricRead, FabricUpdate
from app.services.exceptions import ConflictError, NotFoundError, ValidationError

router = APIRouter(prefix="/fabrics", tags=["fabrics"])


@router.get("", response_model=list[FabricRead], summary="Listar telas del catálogo")
def list_fabrics(
    service: FabricServiceDep,
    pattern: FabricPattern | None = Query(None, description="Filtrar por dibujo"),
    include_inactive: bool = Query(False, description="Incluir telas retiradas"),
    only_probable: bool = Query(
        False,
        description="Solo las que tienen mosaico y por tanto se pueden probar",
    ),
    limit: int = Query(60, ge=1, le=120),
    offset: int = Query(0, ge=0),
) -> list[FabricRead]:
    return service.list(
        pattern=pattern,
        include_inactive=include_inactive,
        only_probable=only_probable,
        limit=limit,
        offset=offset,
    )


@router.get("/{fabric_id}", response_model=FabricRead, summary="Obtener una tela")
def get_fabric(fabric_id: int, service: FabricServiceDep) -> FabricRead:
    try:
        return service.get(fabric_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post(
    "",
    response_model=FabricRead,
    status_code=status.HTTP_201_CREATED,
    summary="Dar de alta una tela (requiere autenticación)",
    responses={401: {"description": "Falta el token o no es válido"}},
)
def create_fabric(
    payload: FabricCreate, service: FabricServiceDep, current_user: CurrentUserDep
) -> FabricRead:
    # `current_user` no se usa en el cuerpo: está aquí para exigir el token. La
    # tela no se atribuye a quien la crea porque el catálogo es de la tienda,
    # no una colección por usuario.
    try:
        return service.create(payload)
    except ConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.patch(
    "/{fabric_id}",
    response_model=FabricRead,
    summary="Editar la ficha de una tela (requiere autenticación)",
)
def update_fabric(
    fabric_id: int,
    payload: FabricUpdate,
    service: FabricServiceDep,
    current_user: CurrentUserDep,
) -> FabricRead:
    try:
        return service.update(fabric_id, payload)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post(
    "/{fabric_id}/photo",
    response_model=FabricRead,
    summary="Subir la fotografía de catálogo (requiere autenticación)",
)
async def upload_photo(
    fabric_id: int,
    service: FabricServiceDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(..., description="JPEG, PNG o WebP"),
) -> FabricRead:
    return await _guardar_imagen(service, fabric_id, file, es_mosaico=False)


@router.post(
    "/{fabric_id}/texture",
    response_model=FabricRead,
    summary="Subir el mosaico que se estampa sobre la prenda",
    description=(
        "Un cuadrado recortado de la tela, que se repita sin costura visible. "
        "NO es la foto de catálogo: esa lleva orillo y dobleces, y al repetirla "
        "sobre una camisa aparecen cuarenta veces."
    ),
)
async def upload_texture(
    fabric_id: int,
    service: FabricServiceDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(..., description="JPEG, PNG o WebP"),
) -> FabricRead:
    return await _guardar_imagen(service, fabric_id, file, es_mosaico=True)


async def _guardar_imagen(
    service, fabric_id: int, file: UploadFile, *, es_mosaico: bool
) -> FabricRead:
    contenido = await file.read()
    try:
        return service.set_image(
            fabric_id,
            content=contenido,
            max_bytes=settings.max_upload_bytes,
            es_mosaico=es_mosaico,
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
