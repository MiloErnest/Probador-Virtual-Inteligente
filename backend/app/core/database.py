"""Conexión a la base de datos y gestión de sesiones.

Decisión técnica: SQLAlchemy **síncrono**, no asíncrono.
Motivo: en esta etapa las consultas son triviales y el modo síncrono es
notablemente más simple de escribir, depurar y testear. FastAPI ejecuta las
dependencias síncronas en un threadpool, así que no bloquea el event loop.
Si en el futuro medimos que la BD es el cuello de botella, migraremos a
`AsyncSession` — pero no antes de tener la medición (Regla 8).
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # descarta conexiones muertas antes de usarlas
    echo=False,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,  # permite leer atributos tras el commit
)


def get_session() -> Generator[Session, None, None]:
    """Dependencia de FastAPI: una sesión de BD por petición."""
    with SessionLocal() as session:
        yield session


def create_tables() -> None:
    """Crea las tablas que aún no existan.

    Suficiente para la Etapa 1. NO gestiona cambios de esquema: en cuanto
    modifiquemos una tabla con datos reales necesitaremos migraciones.
    Alembic es la primera tarea de la Etapa 2 (ver PROJECT_STATUS.md).
    """
    # La importación va aquí, no arriba, para evitar un ciclo de importación
    # y para garantizar que todos los modelos estén registrados en Base.metadata.
    from app.models import Base  # noqa: PLC0415

    Base.metadata.create_all(bind=engine)
