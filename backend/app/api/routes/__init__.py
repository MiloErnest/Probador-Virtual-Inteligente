"""Router raíz de la API.

Un único punto donde se registran todos los routers, de modo que `main.py`
no necesite conocerlos uno a uno.
"""

from fastapi import APIRouter

from app.api.routes import auth, garments, health, try_on, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(garments.router)
api_router.include_router(try_on.router)

__all__ = ["api_router"]
