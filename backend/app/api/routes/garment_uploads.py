"""Endpoints de las prendas que sube el usuario.

Todo aquí exige token, y todo va filtrado por el usuario del token. El diseño
de un taller no se comparte con el taller de al lado.
"""

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, UploadFile, status

from app.api.deps import CurrentUserDep, GarmentUploadServiceDep, SketchRunnerDep
from app.core.config import settings
from app.models.garment_upload import GarmentKind, GarmentStatus
from app.schemas.common import MessageResponse
from app.schemas.garment_upload import GarmentUploadRead
from app.services.exceptions import EmailNotVerifiedError, NotFoundError, ValidationError

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
        "Una **fotografía** ya es la prenda: se recorta y vuelve lista (`ready`).\n\n"
        "Un **boceto** no lo es: la IA generativa lo convierte en la fotografía de "
        "la prenda, y **eso se cobra**. Vuelve en `pending` y hay que sondear "
        "`GET /garment-uploads/{id}` hasta `ready` o `failed`. Las telas se prueban "
        "después sobre esa prenda, con el motor determinista y sin coste."
    ),
)
async def create_upload(
    service: GarmentUploadServiceDep,
    runner: SketchRunnerDep,
    background: BackgroundTasks,
    current_user: CurrentUserDep,
    name: str = Form(..., min_length=1, max_length=160),
    kind: GarmentKind = Form(GarmentKind.PHOTO),
    file: UploadFile = File(..., description="JPEG, PNG o WebP"),
) -> GarmentUploadRead:
    contenido = await file.read()
    try:
        prenda = service.create(
            user_id=current_user.id,
            name=name,
            kind=kind,
            content=contenido,
            max_bytes=settings.max_upload_bytes,
            correo_verificado=current_user.email_verified,
        )
    except EmailNotVerifiedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    if prenda.status is GarmentStatus.PENDING:
        background.add_task(runner, prenda.id)
    return prenda


@router.post(
    "/{upload_id}/variants",
    response_model=GarmentUploadRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generar otra variante de la prenda de un boceto",
    description=(
        "Vuelve a pedirle la prenda a la IA a partir del mismo dibujo. **Cada "
        "llamada se cobra.** Devuelve la prenda que se está generando, en "
        "`pending`: normalmente una nueva, para no pisar la anterior ni las telas "
        "ya probadas sobre ella; la misma, si había fallado."
    ),
)
def create_variant(
    upload_id: int,
    service: GarmentUploadServiceDep,
    runner: SketchRunnerDep,
    background: BackgroundTasks,
    current_user: CurrentUserDep,
) -> GarmentUploadRead:
    try:
        prenda = service.otra_variante(
            upload_id, current_user.id, correo_verificado=current_user.email_verified
        )
    except EmailNotVerifiedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    background.add_task(runner, prenda.id)
    return prenda


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
