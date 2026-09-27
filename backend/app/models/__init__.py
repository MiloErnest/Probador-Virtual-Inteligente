"""Modelos de SQLAlchemy.

Todos los modelos se reexportan aquí para que `Base.metadata` los conozca
con una sola importación (`from app.models import Base`).

UN PRODUCTO, DOS PREGUNTAS
--------------------------
- «¿Cómo queda ESTA prenda con otra tela?»: `Fabric` es el catálogo de la
  tienda, `GarmentUpload` la prenda o el boceto del usuario, y `FabricTrial`
  la prueba.
- «¿Cómo me queda a MÍ?»: `PersonPhoto` es la foto de la persona y `TryOn` la
  prueba sobre ella. La prenda sale del taller —una prueba de tela o una
  prenda subida—, nunca de un catálogo aparte: antes había uno para el
  probador con cámara, y se retiró junto con la cámara.
"""

from app.models.base import Base, TimestampMixin
from app.models.fabric import Fabric, FabricPattern
from app.models.fabric_trial import FabricTrial, TrialMethod, TrialStatus
from app.models.garment_upload import GarmentKind, GarmentUpload
from app.models.person_photo import PersonPhoto
from app.models.try_on import GarmentCategory, TryOn
from app.models.user import User

__all__ = [
    "Base",
    "TimestampMixin",
    "User",
    # Probar telas sobre una prenda.
    "Fabric",
    "FabricPattern",
    "GarmentUpload",
    "GarmentKind",
    "FabricTrial",
    "TrialStatus",
    "TrialMethod",
    # Probarse la prenda.
    "PersonPhoto",
    "TryOn",
    "GarmentCategory",
]
