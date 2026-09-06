"""Endpoints de autenticación.

El registro sigue viviendo en `users.py` (`POST /api/users`), porque crea un
recurso del catálogo de usuarios. Aquí solo está lo relativo a la sesión:
obtener un token y saber a quién pertenece.

No hay endpoint de cierre de sesión. Un JWT es válido hasta que caduca y no
existe lista de revocación en esta etapa (ver PROJECT_STATUS.md), así que un
`POST /auth/logout` no podría invalidar nada: sería un endpoint que finge
hacer algo. Cerrar sesión consiste en que el cliente descarte el token.
"""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AuthServiceDep, CurrentUserDep
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserRead
from app.services.exceptions import AuthenticationError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión y obtener un token",
    responses={401: {"description": "Credenciales incorrectas"}},
)
def login(payload: LoginRequest, service: AuthServiceDep) -> TokenResponse:
    try:
        user = service.authenticate(payload.email, payload.password)
    except AuthenticationError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    access_token, expires_in = service.issue_token(user)
    return TokenResponse(access_token=access_token, expires_in=expires_in)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Datos del usuario autenticado",
    responses={401: {"description": "Falta el token o no es válido"}},
)
def read_current_user(current_user: CurrentUserDep) -> UserRead:
    """Quién soy, según el token que acompaña a la petición.

    El frontend lo usa al cargar para restaurar la sesión: si el token
    guardado sigue siendo válido, aquí obtiene el usuario; si no, recibe un
    401 y borra el token.
    """
    return UserRead.model_validate(current_user)
