"""Modelos de SQLAlchemy.

Todos los modelos se reexportan aquí para que `Base.metadata` los conozca
con una sola importación (`from app.models import Base`).

DOS PRODUCTOS, DOS CATÁLOGOS
----------------------------
- `Fabric` es el catálogo de la tienda textil: el producto que describe el
  Product Vision Board. Sus usuarios son diseñadores y modistas que eligen
  tela, y suben su prenda (`GarmentUpload`) para verla (`FabricTrial`).
- `Garment` es el catálogo del probador con cámara, que es la funcionalidad
  adicional. Son tablas distintas a propósito: una es inventario de la tienda
  y la otra es ropa para probarse delante del espejo.
"""

from app.models.base import Base, TimestampMixin
from app.models.fabric import Fabric, FabricPattern
from app.models.fabric_trial import FabricTrial, TrialMethod, TrialStatus
from app.models.garment import Garment, GarmentCategory, GarmentFabric
from app.models.garment_upload import GarmentKind, GarmentUpload
from app.models.user import User

__all__ = [
    "Base",
    "TimestampMixin",
    "User",
    # Producto principal: probar telas sobre una prenda.
    "Fabric",
    "FabricPattern",
    "GarmentUpload",
    "GarmentKind",
    "FabricTrial",
    "TrialStatus",
    "TrialMethod",
    # Funcionalidad adicional: el probador con cámara.
    "Garment",
    "GarmentCategory",
    "GarmentFabric",
]
