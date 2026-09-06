"""Conexión a la base de datos y gestión de sesiones.

Decisión técnica: SQLAlchemy **síncrono**, no asíncrono.
Motivo: en esta etapa las consultas son triviales y el modo síncrono es
notablemente más simple de escribir, depurar y testear. FastAPI ejecuta las
dependencias síncronas en un threadpool, así que no bloquea el event loop.
Si en el futuro medimos que la BD es el cuello de botella, migraremos a
`AsyncSession` — pero no antes de tener la medición (Regla 8).
"""

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
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
    """Crea las tablas que aún no existan, directamente desde los modelos.

    ATENCIÓN: desde la Etapa 2, el esquema de la base de datos lo gobierna
    Alembic. Esta función YA NO se llama al arrancar la aplicación.

    `create_all` solo crea tablas que faltan; no altera las que ya existen.
    Contra una base con datos, un cambio de columna se ignora en silencio y
    todo parece haber funcionado — que es justo el fallo que motivó poner
    Alembic antes que la autenticación.

    Se conserva únicamente para los tests, que levantan un esquema desechable
    en SQLite desde los metadatos (ver tests/conftest.py). Para cualquier base
    real, la orden correcta es:

        alembic upgrade head
    """
    # La importación va aquí, no arriba, para evitar un ciclo de importación
    # y para garantizar que todos los modelos estén registrados en Base.metadata.
    from app.models import Base  # noqa: PLC0415

    Base.metadata.create_all(bind=engine)


def get_schema_revision() -> str | None:
    """Revisión de Alembic aplicada en la base, o None si no hay ninguna.

    Sirve para distinguir "la base no está migrada" de "la base no responde",
    que producen síntomas muy parecidos y arreglos muy distintos.
    """
    with engine.connect() as connection:
        if not inspect(connection).has_table("alembic_version"):
            return None
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
