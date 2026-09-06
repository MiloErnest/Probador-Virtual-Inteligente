"""Dependencias inyectables de FastAPI.

Aquí se construye el grafo de objetos (sesión -> repositorio -> servicio).
Las rutas solo declaran qué servicio necesitan; no saben cómo se arma.
Esto también permite sustituir cualquier pieza en los tests.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.repositories.garment import GarmentRepository
from app.repositories.try_on_session import TryOnSessionRepository
from app.repositories.user import UserRepository
from app.services.garment import GarmentService
from app.services.storage import Storage, get_storage
from app.services.try_on_session import TryOnSessionService
from app.services.user import UserService

SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[Storage, Depends(get_storage)]


def get_user_service(session: SessionDep) -> UserService:
    return UserService(UserRepository(session))


def get_garment_service(session: SessionDep, storage: StorageDep) -> GarmentService:
    return GarmentService(GarmentRepository(session), storage)


def get_try_on_service(session: SessionDep, storage: StorageDep) -> TryOnSessionService:
    return TryOnSessionService(TryOnSessionRepository(session), storage)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
GarmentServiceDep = Annotated[GarmentService, Depends(get_garment_service)]
TryOnServiceDep = Annotated[TryOnSessionService, Depends(get_try_on_service)]
