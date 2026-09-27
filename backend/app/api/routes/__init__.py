"""Router raíz de la API.

Un único punto donde se registran todos los routers, de modo que `main.py`
no necesite conocerlos uno a uno.

- `fabrics`, `garment_uploads` y `trials`: probar telas sobre una prenda.
- `try_ons`: probarse la prenda — la foto de la persona y la prueba sobre ella.
"""

from fastapi import APIRouter

from app.api.routes import (
    auth,
    fabrics,
    garment_uploads,
    health,
    trials,
    try_ons,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)

# Probar telas sobre una prenda.
api_router.include_router(fabrics.router)
api_router.include_router(garment_uploads.router)
api_router.include_router(trials.router)

# Probarse la prenda.
api_router.include_router(try_ons.photos_router)
api_router.include_router(try_ons.router)

__all__ = ["api_router"]
