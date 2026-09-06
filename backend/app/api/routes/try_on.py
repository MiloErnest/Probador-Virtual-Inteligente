"""Endpoints de sesiones de prueba virtual (solo lectura en la Etapa 1).

Existen para que la pantalla "Mis pruebas" del frontend consuma datos reales
desde el primer día. Devolverán una lista vacía hasta que se implemente la
creación de pruebas con IA.
"""

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import TryOnServiceDep
from app.schemas.try_on_session import TryOnSessionRead
from app.services.exceptions import NotFoundError

router = APIRouter(prefix="/try-on-sessions", tags=["try-on"])


@router.get("", response_model=list[TryOnSessionRead], summary="Historial de pruebas")
def list_try_on_sessions(
    service: TryOnServiceDep,
    user_id: int = Query(..., description="Usuario del que se pide el historial"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[TryOnSessionRead]:
    return service.list_by_user(user_id, limit=limit, offset=offset)


@router.get("/{session_id}", response_model=TryOnSessionRead, summary="Detalle de una prueba")
def get_try_on_session(session_id: int, service: TryOnServiceDep) -> TryOnSessionRead:
    try:
        return service.get(session_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
