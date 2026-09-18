"""Endpoints de las pruebas de tela.

Es el corazón del producto: aquí es donde una prenda y una tela se convierten
en una imagen que ayuda a decidir una compra.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from app.api.deps import CurrentUserDep, TrialRunnerDep, TrialServiceDep
from app.schemas.common import MessageResponse
from app.schemas.fabric_trial import TrialCreate, TrialRead
from app.services.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/trials", tags=["pruebas de tela"])


@router.get("", response_model=list[TrialRead], summary="Mis pruebas")
def list_trials(
    service: TrialServiceDep,
    current_user: CurrentUserDep,
    garment_upload_id: int | None = Query(
        None, description="Solo las de una prenda: es la comparación lado a lado"
    ),
    limit: int = Query(60, ge=1, le=120),
    offset: int = Query(0, ge=0),
) -> list[TrialRead]:
    return service.list(
        current_user.id, garment_upload_id=garment_upload_id, limit=limit, offset=offset
    )


@router.get("/{trial_id}", response_model=TrialRead, summary="Una prueba")
def get_trial(
    trial_id: int, service: TrialServiceDep, current_user: CurrentUserDep
) -> TrialRead:
    try:
        return service.get(trial_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post(
    "",
    response_model=TrialRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Probar una tela sobre una prenda",
    description=(
        "Responde 202 con la prueba en estado `pending`: **el resultado no viene "
        "aquí**. Hay que sondear `GET /trials/{id}` hasta que el estado sea "
        "`completed` o `failed`.\n\n"
        "202 y no 201 porque el recurso existe pero todavía no tiene resultado, "
        "que es exactamente lo que ese código comunica."
    ),
)
def create_trial(
    payload: TrialCreate,
    service: TrialServiceDep,
    runner: TrialRunnerDep,
    background: BackgroundTasks,
    current_user: CurrentUserDep,
) -> TrialRead:
    try:
        prueba = service.create(current_user.id, payload)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    background.add_task(runner, prueba.id)
    return prueba


@router.delete(
    "/{trial_id}", response_model=MessageResponse, summary="Borrar una prueba"
)
def delete_trial(
    trial_id: int, service: TrialServiceDep, current_user: CurrentUserDep
) -> MessageResponse:
    try:
        service.delete(trial_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return MessageResponse(message="Prueba borrada.")
