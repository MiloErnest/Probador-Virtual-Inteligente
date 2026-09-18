"""Endpoints de las prendas que sube el usuario.

Todo aquí exige token, y todo va filtrado por el usuario del token. El diseño
de un taller no se comparte con el taller de al lado.
"""

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from app.api.deps import CurrentUserDep, GarmentUploadServiceDep
from app.core.config import settings
from app.models.garment_upload import GarmentKind
from app.schemas.common import MessageResponse
from app.schemas.garment_upload import GarmentUploadRead
from app.services.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/garment-uploads", tags=["prendas del usuario"])


@router.get("", response_model=list[GarmentUploadRead], summary="Mis prendas")
def list_uploads(
    service: GarmentUploadServiceDep,
    current_user: CurrentUserDep,
    limit: int = Query(60, ge=1, le=120),
    offset: int = Query(0, ge=0),
) -> list[GarmentUploadRead]:
    # El usuario sale del token, NUNCA de un parámetro. Aceptar `?user_id=`
    # permitiría leer los diseños de cualquiera cambiando un número, que es un
    # agujero que este proyecto ya tuvo una vez.
    return service.list(current_user.id, limit=limit, offset=offset)


@router.get("/{upload_id}", response_model=GarmentUploadRead, summary="Una prenda mía")
def get_upload(
    upload_id: int, service: GarmentUploadServiceDep, current_user: CurrentUserDep
) -> GarmentUploadRead:
    try:
        return service.get(upload_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post(
    "",
    response_model=GarmentUploadRead,
    status_code=status.HTTP_201_CREATED,
    summary="Subir una prenda o un boceto",
    description=(
        "El tipo no es una etiqueta: decide qué motor puede vestirla. Una "
        "fotografía trae sus propios pliegues y sombras, y el motor determinista "
        "los reutiliza — gratis y siempre igual. Un boceto no tiene sombras que "
        "reutilizar, así que solo la IA puede vestirlo."
    ),
)
async def create_upload(
    service: GarmentUploadServiceDep,
    current_user: CurrentUserDep,
    name: str = Form(..., min_length=1, max_length=160),
    kind: GarmentKind = Form(GarmentKind.PHOTO),
    file: UploadFile = File(..., description="JPEG, PNG o WebP"),
) -> GarmentUploadRead:
    contenido = await file.read()
    try:
        return service.create(
            user_id=current_user.id,
            name=name,
            kind=kind,
            content=contenido,
            max_bytes=settings.max_upload_bytes,
        )
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.delete(
    "/{upload_id}",
    response_model=MessageResponse,
    summary="Borrar una prenda y sus archivos",
)
def delete_upload(
    upload_id: int, service: GarmentUploadServiceDep, current_user: CurrentUserDep
) -> MessageResponse:
    try:
        service.delete(upload_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return MessageResponse(message="Prenda borrada.")
