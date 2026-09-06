"""Endpoint de comprobación de salud.

Verifica también la base de datos: si el backend responde pero la BD está
caída, el estado es "degraded" (no un error 500). Así el frontend puede
distinguir "el servidor no arranca" de "el servidor arranca pero no hay BD",
que son dos problemas con soluciones distintas.
"""

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import SessionDep
from app.core.config import settings
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Estado del servicio")
def health(session: SessionDep) -> HealthResponse:
    try:
        session.execute(text("SELECT 1"))
        database = "up"
    except Exception:  # noqa: BLE001 - cualquier fallo de BD significa "down"
        database = "down"

    return HealthResponse(
        status="ok" if database == "up" else "degraded",
        service=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        database=database,
    )
