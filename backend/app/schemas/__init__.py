"""Schemas Pydantic: el contrato público de la API."""

from app.schemas.common import HealthResponse, MessageResponse
from app.schemas.fabric import FabricCreate, FabricRead, FabricUpdate
from app.schemas.fabric_trial import TrialCreate, TrialRead
from app.schemas.garment_upload import GarmentUploadRead
from app.schemas.try_on import PersonPhotoRead, TryOnCreate, TryOnRead
from app.schemas.user import UserCreate, UserRead

__all__ = [
    "HealthResponse",
    "MessageResponse",
    "FabricCreate",
    "FabricRead",
    "FabricUpdate",
    "TrialCreate",
    "TrialRead",
    "GarmentUploadRead",
    "PersonPhotoRead",
    "TryOnCreate",
    "TryOnRead",
    "UserCreate",
    "UserRead",
]
