"""Endpoints del perfil corporal y la recomendación de talla (Fase 3).

Todo exige token y todo opera sobre el perfil DEL USUARIO AUTENTICADO. No hay
ningún endpoint que reciba un identificador de usuario: son medidas del cuerpo
de una persona, y la única forma de garantizar que nadie lea las de otro es
que la API no ofrezca la posibilidad de pedirlas.
"""

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from app.api.deps import BodyProfileServiceDep, BodyAnalysisProviderDep, CurrentUserDep
from app.core.config import settings
from app.models.garment import GarmentCategory
from app.schemas.body_profile import (
    BodyProfileRead,
    BodyProfileUpdate,
    SizeRecommendationRead,
)
from app.schemas.common import MessageResponse
from app.services.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/body-profile", tags=["body"])

SIN_TOKEN = {401: {"description": "Falta el token o no es válido"}}


@router.get(
    "",
    response_model=BodyProfileRead,
    summary="Tu perfil corporal",
    responses={**SIN_TOKEN, 404: {"description": "Todavía no tienes perfil"}},
)
def get_body_profile(
    service: BodyProfileServiceDep, current_user: CurrentUserDep
) -> BodyProfileRead:
    try:
        return service.get(current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.put(
    "",
    response_model=BodyProfileRead,
    summary="Crear o actualizar tus medidas",
    responses={**SIN_TOKEN, 422: {"description": "Alguna medida está fuera de rango"}},
)
def upsert_body_profile(
    payload: BodyProfileUpdate,
    service: BodyProfileServiceDep,
    current_user: CurrentUserDep,
) -> BodyProfileRead:
    """PUT y no POST: el perfil es único por usuario y la operación es
    idempotente. Repetir la misma llamada deja el mismo resultado."""
    try:
        return service.upsert(current_user.id, payload)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.post(
    "/analyse",
    response_model=BodyProfileRead,
    summary="Estimar tus medidas a partir de una fotografía",
    responses={**SIN_TOKEN, 422: {"description": "La foto no sirve para el análisis"}},
)
async def analyse_body_photo(
    service: BodyProfileServiceDep,
    current_user: CurrentUserDep,
    provider: BodyAnalysisProviderDep,
    photo: UploadFile = File(..., description="Foto vertical, de cuerpo entero y de frente"),
    height_cm: float | None = Form(
        None, description="Tu altura real en cm. Mejora mucho la estimación."
    ),
) -> BodyProfileRead:
    """Es síncrono: el análisis tarda del orden de un segundo, no minutos, y
    el usuario está esperando. Encolarlo obligaría a sondear para nada."""
    contenido = await photo.read()
    try:
        return service.analyse_photo(
            current_user.id,
            photo=contenido,
            max_bytes=settings.max_upload_bytes,
            provider=provider,
            height_cm=height_cm,
        )
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.delete(
    "",
    response_model=MessageResponse,
    summary="Borrar tu perfil corporal y su fotografía",
    responses={**SIN_TOKEN, 404: {"description": "No tienes perfil"}},
)
def delete_body_profile(
    service: BodyProfileServiceDep, current_user: CurrentUserDep
) -> MessageResponse:
    try:
        service.delete(current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return MessageResponse(message="Perfil corporal eliminado.")


@router.get(
    "/size-recommendation",
    response_model=SizeRecommendationRead,
    summary="Qué talla te corresponde",
    responses={**SIN_TOKEN, 404: {"description": "Falta el perfil o la prenda"}},
)
def size_recommendation(
    service: BodyProfileServiceDep,
    current_user: CurrentUserDep,
    garment_id: int | None = Query(None, description="Prenda concreta del catálogo"),
    category: GarmentCategory | None = Query(
        None, description="Categoría suelta, para diseños propios sin catálogo"
    ),
) -> SizeRecommendationRead:
    """Acepta una prenda o una categoría.

    La categoría existe por los diseños generados en la Fase 2: no están en el
    catálogo, así que no tienen categoría propia y la elige el usuario.
    """
    if (garment_id is None) == (category is None):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Indica una prenda (garment_id) o una categoría, pero no ambas.",
        )

    try:
        if garment_id is not None:
            return service.recommend_size(current_user.id, garment_id)
        return service.recommend_size_for_category(current_user.id, category)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
