"""Endpoints de diseños generados por texto (Fase 2).

Todo exige token: un diseño pertenece a quien lo pidió, y generarlo cuesta
recursos (dinero, cuando el proveedor sea real).

Mismo contrato asíncrono que las pruebas virtuales: 202 con el diseño en
`pending`, y el cliente sondea `GET /{id}` hasta `completed` o `failed`.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from app.api.deps import CurrentUserDep, DesignRunnerDep, DesignServiceDep
from app.schemas.design import DesignCreate, DesignRead, DesignRefine
from app.services.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/designs", tags=["designs"])


@router.post(
    "",
    response_model=DesignRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generar un diseño a partir de una descripción",
    responses={401: {"description": "Falta el token o no es válido"}},
)
def create_design(
    payload: DesignCreate,
    service: DesignServiceDep,
    current_user: CurrentUserDep,
    background_tasks: BackgroundTasks,
    run_job: DesignRunnerDep,
) -> DesignRead:
    try:
        design = service.create(user_id=current_user.id, prompt=payload.prompt)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    background_tasks.add_task(run_job, design.id)
    return design


@router.post(
    "/{design_id}/refine",
    response_model=DesignRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Iterar sobre un diseño existente",
    responses={
        401: {"description": "Falta el token o no es válido"},
        404: {"description": "El diseño no existe o no es tuyo"},
        422: {"description": "El diseño todavía no se ha generado"},
    },
)
def refine_design(
    design_id: int,
    payload: DesignRefine,
    service: DesignServiceDep,
    current_user: CurrentUserDep,
    background_tasks: BackgroundTasks,
    run_job: DesignRunnerDep,
) -> DesignRead:
    """Crea una versión nueva; el diseño original se conserva intacto."""
    try:
        design = service.refine(
            design_id, user_id=current_user.id, refinement=payload.refinement
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    background_tasks.add_task(run_job, design.id)
    return design


@router.get(
    "",
    response_model=list[DesignRead],
    summary="Tus diseños, del más reciente al más antiguo",
    responses={401: {"description": "Falta el token o no es válido"}},
)
def list_designs(
    service: DesignServiceDep,
    current_user: CurrentUserDep,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[DesignRead]:
    return service.list_by_user(current_user.id, limit=limit, offset=offset)


@router.get(
    "/{design_id}",
    response_model=DesignRead,
    summary="Detalle de un diseño propio",
    responses={
        401: {"description": "Falta el token o no es válido"},
        404: {"description": "El diseño no existe o no es tuyo"},
    },
)
def get_design(
    design_id: int, service: DesignServiceDep, current_user: CurrentUserDep
) -> DesignRead:
    try:
        return service.get_for_user(design_id, user_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
