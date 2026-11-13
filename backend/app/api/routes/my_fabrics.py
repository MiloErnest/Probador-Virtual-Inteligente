"""Las telas del propio taller (Ep6-Hu7 a Hu11).

El catálogo (`/api/fabrics`) es el de la tienda y lo ve cualquiera. Aquí están
las telas que cada usuario fotografía en su taller: solo las ve él, y con ellas
prueba sus prendas igual que con las del catálogo.

Todo exige token, y el dueño sale SIEMPRE del token, nunca de un parámetro. Una
tela de otro responde 404, no 403: un 403 confirmaría que existe.

El mosaico se calcula con el motor determinista (`app/textil/tela_propia.py`):
sin IA generativa, sin coste.
"""

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status

from app.api.deps import CurrentUserDep, FabricServiceDep
from app.core.config import settings
from app.models.fabric import FabricPattern
from app.schemas.fabric import FabricPreview, FabricRead, OwnFabricCreated, OwnFabricUpdate
from app.services.exceptions import ConflictError, NotFoundError, ValidationError

router = APIRouter(prefix="/my-fabrics", tags=["my-fabrics"])


@router.get("", response_model=list[FabricRead], summary="Listar mis telas")
def list_my_fabrics(
    service: FabricServiceDep,
    current_user: CurrentUserDep,
    include_retired: bool = Query(
        False,
        description=(
            "Incluir las borradas que tienen pruebas. Sirve al historial, que "
            "sigue necesitando su nombre."
        ),
    ),
) -> list[FabricRead]:
    return service.list_own(current_user.id, include_retired=include_retired)


@router.post(
    "/preview",
    response_model=FabricPreview,
    summary="Calcular el mosaico de una foto, sin guardar nada",
    description=(
        "Devuelve el mosaico que saldría de la foto, su junta medida y los avisos "
        "sobre la foto (pequeña, desenfocada, luz desigual). No guarda nada."
    ),
)
async def preview_my_fabric(
    service: FabricServiceDep,
    current_user: CurrentUserDep,
    pattern: FabricPattern = Form(..., description="solid, stripes o print"),
    file: UploadFile = File(..., description="JPEG, PNG o WebP"),
) -> FabricPreview:
    contenido = await file.read()
    try:
        return service.preview_own(content=contenido, max_bytes=settings.max_upload_bytes, tipo=pattern)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.post(
    "",
    response_model=OwnFabricCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Añadir una tela de mi taller desde una foto",
)
async def create_my_fabric(
    service: FabricServiceDep,
    current_user: CurrentUserDep,
    name: str = Form(..., min_length=1, max_length=160),
    pattern: FabricPattern = Form(..., description="solid, stripes o print"),
    composition: str | None = Form(None, max_length=160),
    default_repeat: int = Form(6, ge=1, le=40),
    file: UploadFile = File(..., description="JPEG, PNG o WebP"),
) -> OwnFabricCreated:
    contenido = await file.read()
    try:
        return service.create_own(
            current_user.id,
            name=name,
            tipo=pattern,
            content=contenido,
            max_bytes=settings.max_upload_bytes,
            composition=composition,
            default_repeat=default_repeat,
        )
    except ConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.get("/{fabric_id}", response_model=FabricRead, summary="Obtener una tela mía")
def get_my_fabric(fabric_id: int, service: FabricServiceDep, current_user: CurrentUserDep) -> FabricRead:
    try:
        return service.get_own(fabric_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.patch("/{fabric_id}", response_model=FabricRead, summary="Editar una tela mía")
def update_my_fabric(
    fabric_id: int,
    payload: OwnFabricUpdate,
    service: FabricServiceDep,
    current_user: CurrentUserDep,
) -> FabricRead:
    try:
        return service.update_own(fabric_id, current_user.id, payload)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.delete(
    "/{fabric_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar una tela mía",
    description=(
        "Si la tela tiene pruebas, se retira y las pruebas se conservan; si no, "
        "se borra con sus imágenes."
    ),
)
def delete_my_fabric(fabric_id: int, service: FabricServiceDep, current_user: CurrentUserDep) -> Response:
    try:
        service.delete_own(fabric_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
