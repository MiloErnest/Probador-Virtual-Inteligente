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
from app.repositories.fabric import FabricRepository
from app.repositories.fabric_trial import FabricTrialRepository
from app.repositories.garment_upload import GarmentUploadRepository
from app.repositories.person_photo import PersonPhotoRepository
from app.repositories.try_on import TryOnRepository
from app.repositories.user import UserRepository
from app.services.auth import AuthService
from app.services.exceptions import AuthenticationError
from app.services.fabric import FabricService
from app.services.fabric_trial import FabricTrialService
from app.services.garment_upload import GarmentUploadService
from app.services.storage import Storage, get_storage
from app.services.trial_jobs import run_trial_job, run_try_on_job
from app.services.try_on import PersonPhotoService, TryOnService
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


def get_fabric_service(session: SessionDep, storage: StorageDep) -> FabricService:
    return FabricService(FabricRepository(session), storage)


def get_garment_upload_service(
    session: SessionDep, storage: StorageDep
) -> GarmentUploadService:
    return GarmentUploadService(GarmentUploadRepository(session), storage)


def get_trial_service(session: SessionDep, storage: StorageDep) -> FabricTrialService:
    return FabricTrialService(
        FabricTrialRepository(session),
        GarmentUploadRepository(session),
        FabricRepository(session),
        storage,
    )


def get_trial_runner() -> Callable[[int], None]:
    """Función que procesa una prueba en segundo plano.

    Se inyecta en lugar de llamar a `run_trial_job` directamente desde la ruta
    por una razón concreta: esa función abre su PROPIA sesión de base de datos
    con `SessionLocal`, que en los tests apunta a PostgreSQL y no a la base
    SQLite de prueba. Pasando por una dependencia, `conftest.py` puede
    sustituirla por una que use la sesión del test.
    """
    return run_trial_job


def get_person_photo_service(session: SessionDep, storage: StorageDep) -> PersonPhotoService:
    return PersonPhotoService(PersonPhotoRepository(session), TryOnRepository(session), storage)


def get_try_on_service(session: SessionDep, storage: StorageDep) -> TryOnService:
    return TryOnService(
        TryOnRepository(session),
        PersonPhotoRepository(session),
        FabricTrialRepository(session),
        GarmentUploadRepository(session),
        storage,
    )


def get_try_on_runner() -> Callable[[int], None]:
    """Igual que `get_trial_runner`: inyectable para que los tests no abran
    la sesión de PostgreSQL."""
    return run_try_on_job


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
FabricServiceDep = Annotated[FabricService, Depends(get_fabric_service)]
GarmentUploadServiceDep = Annotated[
    GarmentUploadService, Depends(get_garment_upload_service)
]
TrialServiceDep = Annotated[FabricTrialService, Depends(get_trial_service)]
TrialRunnerDep = Annotated[Callable[[int], None], Depends(get_trial_runner)]
PersonPhotoServiceDep = Annotated[PersonPhotoService, Depends(get_person_photo_service)]
TryOnServiceDep = Annotated[TryOnService, Depends(get_try_on_service)]
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
