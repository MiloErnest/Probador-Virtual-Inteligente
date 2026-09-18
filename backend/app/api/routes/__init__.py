"""Router raíz de la API.

Un único punto donde se registran todos los routers, de modo que `main.py`
no necesite conocerlos uno a uno.

Dos productos conviven aquí:
  - `fabrics`, `garment_uploads` y `trials` son el probador de telas, que es
    lo que describe el Product Vision Board.
  - `garments` es el catálogo del probador con cámara, la funcionalidad
    adicional.
"""

from fastapi import APIRouter

from app.api.routes import (
    auth,
    fabrics,
    garment_uploads,
    garments,
    health,
    trials,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)

# Producto principal: probar telas sobre una prenda.
api_router.include_router(fabrics.router)
api_router.include_router(garment_uploads.router)
api_router.include_router(trials.router)

# Funcionalidad adicional: el probador con cámara.
api_router.include_router(garments.router)

__all__ = ["api_router"]
