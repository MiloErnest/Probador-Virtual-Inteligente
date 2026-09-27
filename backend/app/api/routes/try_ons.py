"""Endpoints del probador: fotos de persona y pruebas sobre ellas.

Todo exige token y todo va filtrado por el usuario del token: son fotos de
personas. Un recurso ajeno responde 404, nunca 403.
"""

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile, status

from app.api.deps import (
    CurrentUserDep,
    PersonPhotoServiceDep,
    TryOnRunnerDep,
    TryOnServiceDep,
)
from app.core.config import settings
from app.schemas.common import MessageResponse
from app.schemas.try_on import PersonPhotoRead, TryOnCreate, TryOnRead
from app.services.exceptions import NotFoundError, ValidationError

photos_router = APIRouter(prefix="/person-photos", tags=["probador"])
router = APIRouter(prefix="/try-ons", tags=["probador"])


# --- Fotos de persona ---------------------------------------------------------


@photos_router.get("", response_model=list[PersonPhotoRead], summary="Mis fotos")
def list_photos(service: PersonPhotoServiceDep, current_user: CurrentUserDep) -> list[PersonPhotoRead]:
    return service.list(current_user.id)


@photos_router.post(
    "",
    response_model=PersonPhotoRead,
    status_code=status.HTTP_201_CREATED,
    summary="Subir una foto de una persona",
    description=(
        "Se guarda enderezada, a 2048 px como máximo y **sin metadatos**: la "
        "ubicación y el modelo del teléfono no llegan al servidor."
    ),
)
async def create_photo(
    service: PersonPhotoServiceDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(..., description="JPEG, PNG o WebP"),
) -> PersonPhotoRead:
    contenido = await file.read()
    try:
        return service.create(
            user_id=current_user.id, content=contenido, max_bytes=settings.max_upload_bytes
        )
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@photos_router.delete(
    "/{photo_id}",
    response_model=MessageResponse,
    summary="Borrar una foto y todas las pruebas hechas con ella",
)
def delete_photo(
    photo_id: int, service: PersonPhotoServiceDep, current_user: CurrentUserDep
) -> MessageResponse:
    try:
        service.delete(photo_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return MessageResponse(message="Foto borrada, con sus pruebas.")


# --- Pruebas sobre persona ----------------------------------------------------


@router.get("", response_model=list[TryOnRead], summary="Mis pruebas sobre persona")
def list_try_ons(
    service: TryOnServiceDep,
    current_user: CurrentUserDep,
    person_photo_id: int | None = Query(None, description="Solo las de una foto"),
    limit: int = Query(60, ge=1, le=120),
    offset: int = Query(0, ge=0),
) -> list[TryOnRead]:
    return service.list(
        current_user.id, person_photo_id=person_photo_id, limit=limit, offset=offset
    )


@router.get("/{try_on_id}", response_model=TryOnRead, summary="Una prueba sobre persona")
def get_try_on(try_on_id: int, service: TryOnServiceDep, current_user: CurrentUserDep) -> TryOnRead:
    try:
        return service.get(try_on_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post(
    "",
    response_model=TryOnRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ponerle una prenda del taller a la persona de una foto",
    description=(
        "La prenda sale de una prueba de tela (`fabric_trial_id`, se usa la imagen "
        "ya generada) o de una prenda subida (`garment_upload_id`). Responde 202 "
        "en `pending`: hay que sondear `GET /try-ons/{id}`."
    ),
)
def create_try_on(
    payload: TryOnCreate,
    service: TryOnServiceDep,
    runner: TryOnRunnerDep,
    background: BackgroundTasks,
    current_user: CurrentUserDep,
) -> TryOnRead:
    try:
        prueba = service.create(current_user.id, payload)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    background.add_task(runner, prueba.id)
    return prueba


@router.delete("/{try_on_id}", response_model=MessageResponse, summary="Borrar una prueba")
def delete_try_on(
    try_on_id: int, service: TryOnServiceDep, current_user: CurrentUserDep
) -> MessageResponse:
    try:
        service.delete(try_on_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return MessageResponse(message="Prueba borrada.")
