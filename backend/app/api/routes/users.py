"""Endpoints de usuarios.

El registro es público, por necesidad: no se puede exigir un token para crear
la cuenta con la que se obtiene el token.

`GET /api/users`, que devolvía la lista completa de usuarios con sus correos
sin pedir nada, se eliminó en la Etapa 2. No tenía ningún consumidor (el
frontend nunca lo llamó) y no existe la figura de administrador que lo
justificara. Volverá el día que haya un panel que realmente lo necesite, y
entonces con el control de acceso que corresponda.
"""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserDep, UserServiceDep
from app.schemas.user import UserCreate, UserRead
from app.services.exceptions import ConflictError

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


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Obtener un usuario",
    responses={
        401: {"description": "Falta el token o no es válido"},
        404: {"description": "El usuario no existe o no es el tuyo"},
    },
)
def get_user(user_id: int, current_user: CurrentUserDep) -> UserRead:
    """Solo puedes consultar tu propia cuenta.

    Pedir la cuenta de otro devuelve 404, no 403. Un 403 confirmaría que ese
    usuario existe, y recorrer los identificadores bastaría para contar
    cuántas cuentas hay registradas. Con 404, "no existe" y "no es tuyo" son
    indistinguibles desde fuera.

    Ya no hace falta consultar la base: el usuario autenticado viene resuelto
    en la dependencia, y es el único que esta ruta puede devolver.
    """
    if user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No existe el usuario {user_id}.")
    return UserRead.model_validate(current_user)
