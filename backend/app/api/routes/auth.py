"""Endpoints de autenticación.

El registro sigue viviendo en `users.py` (`POST /api/users`), porque crea un
recurso del catálogo de usuarios. Aquí solo está lo relativo a la sesión:
iniciarla, cerrarla y saber a quién pertenece.

LA SESIÓN DEL NAVEGADOR VA EN UNA COOKIE `httpOnly` (Ep5-Hu6)
------------------------------------------------------------
Hasta el 12/11/2026 el frontend guardaba el token en `localStorage`, al
alcance de cualquier script de la página: un fallo de XSS se lo llevaba. Ahora
`login` lo deja en una cookie que ningún script puede leer, y el frontend ya no
lo guarda. El token sigue viniendo también en el cuerpo, para las pruebas y
para quien use la API con la cabecera `Bearer`.

Con la cookie sí tiene sentido un `logout`: el script del frontend no puede
borrar una cookie `httpOnly`, así que la borra el servidor. Lo que NO hace es
revocar el JWT: si alguien lo copió, sigue valiendo hasta que caduca, porque no
hay lista de revocación. Lo que sí garantiza es que el navegador ya no lo
manda.
"""

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import COOKIE_DE_SESION, AuthServiceDep, CurrentUserDep
from app.core.config import settings
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserRead
from app.services.exceptions import AuthenticationError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión",
    description=(
        "Deja la sesión en una cookie `httpOnly` para el navegador y devuelve "
        "también el token, para usarlo con `Authorization: Bearer`."
    ),
    responses={401: {"description": "Credenciales incorrectas"}},
)
def login(payload: LoginRequest, service: AuthServiceDep, response: Response) -> TokenResponse:
    try:
        user = service.authenticate(payload.email, payload.password)
    except AuthenticationError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    access_token, expires_in = service.issue_token(user)
    response.set_cookie(
        COOKIE_DE_SESION,
        access_token,
        max_age=expires_in,
        httponly=True,
        # Lax: no viaja en las peticiones que otra web dispara contra esta
        # (salvo navegar a ella), que es lo que permite un CSRF.
        samesite="lax",
        # En local la aplicación va por http; en producción, solo por https.
        secure=settings.ENVIRONMENT == "production",
        # Solo la API la necesita; las imágenes de /media son públicas.
        path=settings.API_PREFIX,
    )
    return TokenResponse(access_token=access_token, expires_in=expires_in)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cerrar sesión en este navegador",
    description=(
        "Borra la cookie de sesión. No revoca el token: un token copiado sigue "
        "valiendo hasta que caduca."
    ),
)
def logout() -> Response:
    # Sin exigir sesión: cerrar una sesión ya caducada tiene que funcionar.
    respuesta = Response(status_code=status.HTTP_204_NO_CONTENT)
    respuesta.delete_cookie(
        COOKIE_DE_SESION,
        path=settings.API_PREFIX,
        httponly=True,
        samesite="lax",
        secure=settings.ENVIRONMENT == "production",
    )
    return respuesta


@router.get(
    "/me",
    response_model=UserRead,
    summary="Datos del usuario autenticado",
    responses={401: {"description": "Falta el token o no es válido"}},
)
def read_current_user(current_user: CurrentUserDep) -> UserRead:
    """Quién soy, según la sesión que acompaña a la petición.

    El frontend lo usa al cargar para restaurar la sesión: si la cookie sigue
    siendo válida, aquí obtiene el usuario; si no, recibe un 401 y empieza sin
    sesión.
    """
    return UserRead.model_validate(current_user)
