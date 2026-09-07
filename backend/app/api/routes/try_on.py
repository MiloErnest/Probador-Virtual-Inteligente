"""Endpoints de sesiones de prueba virtual.

Etapa 2: el usuario ya no llega en `?user_id=`, sale del token. Aquel
parámetro no era solo una comodidad temporal, era un agujero: cualquiera
podía leer el historial de otro cambiando un número en la URL.

Fase 1: se puede crear una prueba. El endpoint de creación responde
**inmediatamente** con la prueba en estado `pending` y deja el trabajo lento
en una tarea de fondo. El cliente sondea `GET /{id}` hasta que el estado sea
`completed` o `failed`.

Se devuelve 202 y no 201 a propósito: 201 significa "creado y listo", y aquí
el recurso existe pero todavía no tiene resultado.
"""

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, UploadFile, status

from app.api.deps import CurrentUserDep, TryOnRunnerDep, TryOnServiceDep
from app.core.config import settings
from app.schemas.try_on_session import TryOnSessionRead
from app.services.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/try-on-sessions", tags=["try-on"])


@router.post(
    "",
    response_model=TryOnSessionRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Crear una prueba virtual (foto + prenda)",
    responses={
        401: {"description": "Falta el token o no es válido"},
        404: {"description": "La prenda o el diseño no existen"},
        422: {"description": "La foto no es válida, o no se indicó exactamente un origen"},
    },
)
async def create_try_on_session(
    service: TryOnServiceDep,
    current_user: CurrentUserDep,
    background_tasks: BackgroundTasks,
    run_job: TryOnRunnerDep,
    photo: UploadFile = File(..., description="Fotografía de la persona (JPEG, PNG o WebP)"),
    garment_id: int | None = Form(
        None, description="Prenda del catálogo que se quiere probar"
    ),
    design_id: int | None = Form(
        None, description="Diseño propio generado en la Fase 2"
    ),
) -> TryOnSessionRead:
    """Registra la prueba y encola su procesado.

    Es `multipart/form-data` porque lleva un archivo. Los identificadores
    viajan como campos de formulario, no como JSON: no se pueden mezclar
    ambos en una misma petición.

    Hay que indicar `garment_id` O `design_id`, nunca los dos. El servicio
    lo valida y la base de datos lo impone con una CHECK.
    """
    content = await photo.read()

    try:
        session = service.create(
            user_id=current_user.id,
            garment_id=garment_id,
            design_id=design_id,
            photo=content,
            max_bytes=settings.max_upload_bytes,
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    # Se encola DESPUÉS de que la fila exista y sin usar el servicio de esta
    # petición: la tarea abre su propia sesión de base de datos, porque la de
    # aquí ya estará cerrada cuando llegue a ejecutarse.
    background_tasks.add_task(run_job, session.id)

    return session


@router.get(
    "",
    response_model=list[TryOnSessionRead],
    summary="Historial de pruebas del usuario autenticado",
    responses={401: {"description": "Falta el token o no es válido"}},
)
def list_try_on_sessions(
    service: TryOnServiceDep,
    current_user: CurrentUserDep,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[TryOnSessionRead]:
    return service.list_by_user(current_user.id, limit=limit, offset=offset)


@router.get(
    "/{session_id}",
    response_model=TryOnSessionRead,
    summary="Detalle de una prueba propia",
    responses={
        401: {"description": "Falta el token o no es válido"},
        404: {"description": "La prueba no existe o no es tuya"},
    },
)
def get_try_on_session(
    session_id: int, service: TryOnServiceDep, current_user: CurrentUserDep
) -> TryOnSessionRead:
    """Una prueba ajena responde 404, igual que una inexistente.

    Con un 403 se podría averiguar cuántas pruebas hay en el sistema
    recorriendo identificadores. El servicio se encarga de la comprobación:
    decidir de quién es un recurso es una regla de negocio, no de transporte.
    """
    try:
        return service.get_for_user(session_id, user_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
