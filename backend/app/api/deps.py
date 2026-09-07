"""Dependencias inyectables de FastAPI.

Aquí se construye el grafo de objetos (sesión -> repositorio -> servicio).
Las rutas solo declaran qué servicio necesitan; no saben cómo se arma.
Esto también permite sustituir cualquier pieza en los tests.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.models.user import User
from app.repositories.garment import GarmentRepository
from app.repositories.try_on_session import TryOnSessionRepository
from app.repositories.user import UserRepository
from app.services.auth import AuthService
from app.services.exceptions import AuthenticationError
from app.services.garment import GarmentService
from app.services.storage import Storage, get_storage
from app.services.try_on_jobs import run_try_on_job
from app.services.try_on_session import TryOnSessionService
from app.services.user import UserService

SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[Storage, Depends(get_storage)]

# `auto_error=False`: sin esto, FastAPI devuelve un 403 cuando falta la
# cabecera Authorization, que es el código equivocado. "No te has
# identificado" es 401; 403 significa "sé quién eres y aun así no puedes".
# Al desactivarlo, la ausencia de cabecera llega aquí como None y la
# tratamos nosotros.
bearer_scheme = HTTPBearer(auto_error=False, description="Token devuelto por /api/auth/login")

CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def get_user_service(session: SessionDep) -> UserService:
    return UserService(UserRepository(session))


def get_auth_service(session: SessionDep) -> AuthService:
    return AuthService(UserRepository(session))


def get_garment_service(session: SessionDep, storage: StorageDep) -> GarmentService:
    return GarmentService(GarmentRepository(session), storage)


def get_try_on_service(session: SessionDep, storage: StorageDep) -> TryOnSessionService:
    return TryOnSessionService(
        TryOnSessionRepository(session), GarmentRepository(session), storage
    )


def get_try_on_runner() -> Callable[[int], None]:
    """Funcion que procesa una prueba en segundo plano.

    Se inyecta en lugar de llamar a `run_try_on_job` directamente desde la
    ruta por una razon concreta: esa funcion abre su PROPIA sesion de base de
    datos con `SessionLocal`, que en los tests apunta a PostgreSQL y no a la
    base SQLite de prueba. Pasando por una dependencia, `conftest.py` puede
    sustituirla por una que use la sesion del test.
    """
    return run_try_on_job


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
GarmentServiceDep = Annotated[GarmentService, Depends(get_garment_service)]
TryOnServiceDep = Annotated[TryOnSessionService, Depends(get_try_on_service)]
TryOnRunnerDep = Annotated[Callable[[int], None], Depends(get_try_on_runner)]


def get_current_user(
    credentials: CredentialsDep, auth_service: AuthServiceDep
) -> User:
    """Usuario autenticado a partir de la cabecera `Authorization: Bearer`.

    Es el único punto del proyecto que convierte un token en un usuario.
    Declararla en una ruta es lo que la convierte en protegida.

    Responde 401 —nunca 403— tanto si falta el token como si es inválido o
    ha caducado, siempre con el mismo mensaje: decir *por qué* falló un token
    solo le sirve a quien está intentando fabricar uno.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado. Inicia sesión para continuar.",
        # Exigida por el estándar HTTP en toda respuesta 401. Es lo que
        # indica al cliente qué tipo de credencial se espera.
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        return auth_service.resolve_token(credentials.credentials)
    except AuthenticationError as exc:
        raise unauthorized from exc


CurrentUserDep = Annotated[User, Depends(get_current_user)]
