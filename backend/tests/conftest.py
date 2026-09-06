"""Configuración de pruebas.

DECISIÓN TÉCNICA
----------------
Los tests usan SQLite en memoria en lugar de PostgreSQL. Ventaja: `pytest`
funciona sin levantar Docker, cada test parte de una base limpia y la suite
tarda menos de un segundo.

Limitación conocida y aceptada en esta etapa: SQLite no es PostgreSQL. No se
validan tipos específicos de PG, constraints avanzadas ni comportamiento
concurrente. Es asumible mientras el esquema sea simple y portable (por eso
los enums se declaran con `native_enum=False`). Cuando aparezcan consultas
dependientes de PostgreSQL habrá que añadir una base de pruebas real.

El almacenamiento también se sustituye por un directorio temporal, de modo
que ningún test escriba en `backend/storage/`.
"""

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_session
from app.main import app
from app.models import Base
from app.services.storage import LocalStorage, Storage, get_storage


@pytest.fixture
def engine():
    # StaticPool + una sola conexión: todas las sesiones comparten la misma
    # base en memoria (sin esto, cada conexión vería una base distinta).
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def db_session(engine) -> Generator[Session, None, None]:
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with TestSession() as session:
        yield session


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    local = LocalStorage(
        root=tmp_path / "storage",
        media_url_path="/media",
        public_base_url="http://testserver",
    )
    local.ensure_directories()
    return local


@pytest.fixture
def client(db_session: Session, storage: Storage) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_storage] = lambda: storage

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
