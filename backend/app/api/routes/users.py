"""Endpoints de usuarios.

Etapa 1: registro y consulta. El login con JWT es la primera tarea de la
Etapa 2; hasta entonces NO hay protección de endpoints, y por eso este
backend no debe exponerse fuera de localhost.
"""

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import UserServiceDep
from app.schemas.user import UserCreate, UserRead
from app.services.exceptions import ConflictError, NotFoundError

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un usuario",
)
def create_user(payload: UserCreate, service: UserServiceDep) -> UserRead:
    try:
        user = service.register(payload)
    except ConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return UserRead.model_validate(user)


@router.get("", response_model=list[UserRead], summary="Listar usuarios")
def list_users(
    service: UserServiceDep,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[UserRead]:
    return [UserRead.model_validate(u) for u in service.list(limit=limit, offset=offset)]


@router.get("/{user_id}", response_model=UserRead, summary="Obtener un usuario")
def get_user(user_id: int, service: UserServiceDep) -> UserRead:
    try:
        user = service.get(user_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return UserRead.model_validate(user)
