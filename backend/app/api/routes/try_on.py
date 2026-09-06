"""Endpoints de sesiones de prueba virtual (solo lectura en la Etapa 1).

Existen para que la pantalla "Mis pruebas" del frontend consuma datos reales
desde el primer día. Devolverán una lista vacía hasta que se implemente la
creación de pruebas con IA.

Etapa 2: el usuario ya no llega en `?user_id=`, sale del token. Aquel
parámetro no era solo una comodidad temporal, era un agujero: cualquiera
podía leer el historial de otro cambiando un número en la URL.
"""

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUserDep, TryOnServiceDep
from app.schemas.try_on_session import TryOnSessionRead
from app.services.exceptions import NotFoundError

router = APIRouter(prefix="/try-on-sessions", tags=["try-on"])


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
