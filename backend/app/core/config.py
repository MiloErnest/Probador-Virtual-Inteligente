"""Configuración de la aplicación.

Toda la configuración se lee de variables de entorno (o del archivo `.env`).
Ningún secreto vive en el código fuente (Regla 9).

`Settings` es la única fuente de verdad: si un módulo necesita un valor
configurable, lo pide aquí en lugar de leer `os.environ` por su cuenta.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents[0]=core, [1]=app, [2]=backend
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Aplicación ---
    PROJECT_NAME: str = "Probador Virtual Inteligente"
    VERSION: str = "0.1.0"
    API_PREFIX: str = "/api"
    ENVIRONMENT: Literal["local", "test", "production"] = "local"
    DEBUG: bool = True

    # --- Seguridad ---
    SECRET_KEY: str = "clave-insegura-solo-para-desarrollo"

    # --- Base de datos ---
    DATABASE_URL: str = "postgresql+psycopg://vfit:vfit_dev_password@localhost:5432/vfit"

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # --- Almacenamiento de imágenes ---
    STORAGE_DIR: Path = BACKEND_DIR / "storage"
    MEDIA_URL_PATH: str = "/media"
    PUBLIC_BASE_URL: str = "http://localhost:8000"
    MAX_UPLOAD_MB: int = 8

    # --- Proveedor de IA (reservado para Fase 2) ---
    AI_PROVIDER: str = "none"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Permite definir CORS_ORIGINS como lista separada por comas en el .env."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Instancia cacheada: el .env se lee una sola vez por proceso."""
    return Settings()


settings = get_settings()
