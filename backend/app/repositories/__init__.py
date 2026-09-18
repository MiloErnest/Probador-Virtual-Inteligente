"""Capa de acceso a datos."""

from app.repositories.fabric import FabricRepository
from app.repositories.fabric_trial import FabricTrialRepository
from app.repositories.garment import GarmentRepository
from app.repositories.garment_upload import GarmentUploadRepository
from app.repositories.user import UserRepository

__all__ = [
    "FabricRepository",
    "FabricTrialRepository",
    "GarmentRepository",
    "GarmentUploadRepository",
    "UserRepository",
]
