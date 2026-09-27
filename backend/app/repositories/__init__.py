"""Capa de acceso a datos."""

from app.repositories.fabric import FabricRepository
from app.repositories.fabric_trial import FabricTrialRepository
from app.repositories.garment_upload import GarmentUploadRepository
from app.repositories.person_photo import PersonPhotoRepository
from app.repositories.try_on import TryOnRepository
from app.repositories.user import UserRepository

__all__ = [
    "FabricRepository",
    "FabricTrialRepository",
    "GarmentUploadRepository",
    "PersonPhotoRepository",
    "TryOnRepository",
    "UserRepository",
]
