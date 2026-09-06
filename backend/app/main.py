"""Punto de entrada de la aplicación FastAPI.

Ejecutar en desarrollo:
    uvicorn app.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import api_router
from app.core.config import settings
from app.core.database import create_tables
from app.services.storage import LocalStorage, get_storage

logger = logging.getLogger("app")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Carpetas de almacenamiento: se crean siempre, no dependen de la BD.
    storage = get_storage()
    if isinstance(storage, LocalStorage):
        storage.ensure_directories()

    # La aplicación arranca aunque PostgreSQL no esté disponible. Así el
    # frontend puede consultar /api/health y mostrar un diagnóstico claro
    # ("backend arriba, base de datos caída") en lugar de un error de red.
    try:
        create_tables()
        logger.info("Tablas verificadas correctamente.")
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "No se pudo conectar a la base de datos al arrancar: %s. "
            "La API responderá, pero /api/health indicará database=down.",
            exc,
        )

    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "API del Probador Virtual Inteligente. "
        "Etapa 1: catálogo, usuarios y almacenamiento de imágenes."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sirve las imágenes subidas en /media/<clave>.
# Aceptable en desarrollo y en un despliegue de un solo servidor. En
# producción real conviene delegarlo en Nginx o en un CDN.
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
app.mount(
    settings.MEDIA_URL_PATH,
    StaticFiles(directory=settings.STORAGE_DIR),
    name="media",
)

app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "health": f"{settings.API_PREFIX}/health",
    }
