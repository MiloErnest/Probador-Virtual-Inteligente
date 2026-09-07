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

from app.ai import get_try_on_provider
from app.api.deps import get_try_on_runner
from app.core.database import get_session
from app.main import app
from app.models import Base
from app.repositories.garment import GarmentRepository
from app.repositories.try_on_session import TryOnSessionRepository
from app.services.storage import LocalStorage, Storage, get_storage
from app.services.try_on_session import TryOnSessionService


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

    # La tarea de fondo real (`run_try_on_job`) abre su PROPIA sesion con
    # `SessionLocal`, que apunta a PostgreSQL. Sin esta sustitucion, crear una
    # prueba en un test escribiria en la base de desarrollo. Aqui se ejecuta
    # el mismo servicio, pero contra la base SQLite del test.
    #
    # TestClient ejecuta las tareas de fondo de forma SINCRONA al terminar la
    # peticion, asi que al volver de `client.post(...)` la prueba ya esta
    # procesada. Comodo para testear, distinto de produccion: eso lo cubre la
    # verificacion manual contra el servidor real.
    def runner_de_prueba(session_id: int) -> None:
        service = TryOnSessionService(
            TryOnSessionRepository(db_session),
            GarmentRepository(db_session),
            storage,
        )
        service.process(session_id, provider=get_try_on_provider())

    app.dependency_overrides[get_try_on_runner] = lambda: runner_de_prueba

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# --- Autenticación (Etapa 2) -------------------------------------------------
#
# Casi todos los endpoints exigen ahora un token. Estas utilidades evitan que
# cada prueba repita el registro y el login.

REGISTERED_USER = {
    "name": "Ana Torres",
    "email": "ana@example.com",
    "password": "contrasena-segura-1",
}


def register_and_login(
    client: TestClient, **overrides: str
) -> tuple[dict[str, object], str]:
    """Registra un usuario y devuelve `(usuario, token)`.

    Recorre los endpoints reales en lugar de insertar en la base y firmar un
    token a mano: así la prueba también verifica que registro y login encajan
    entre sí, que es donde suelen aparecer los fallos.
    """
    payload = {**REGISTERED_USER, **overrides}

    created = client.post("/api/users", json=payload)
    assert created.status_code == 201, created.text

    logged_in = client.post(
        "/api/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert logged_in.status_code == 200, logged_in.text

    return created.json(), logged_in.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_token(client: TestClient) -> tuple[dict[str, object], str]:
    """Usuario registrado y con sesión iniciada."""
    return register_and_login(client)


@pytest.fixture
def auth_client(client: TestClient, user_token: tuple[dict[str, object], str]) -> TestClient:
    """Cliente que envía el token en todas sus peticiones.

    Para las pruebas que solo necesitan "estar autenticadas" y no les importa
    quién sea el usuario.
    """
    _, token = user_token
    client.headers.update(auth_headers(token))
    return client


# --- Imágenes de prueba (Fase 1) ---------------------------------------------
#
# Se generan con Pillow en vez de incrustar bytes en base64: así son imágenes
# de verdad, con el tamaño que cada prueba necesita, y se ve de un vistazo qué
# representan.


def make_image_bytes(
    width: int = 400, height: int = 600, color: str = "navy", fmt: str = "PNG"
) -> bytes:
    """Devuelve los bytes de una imagen real del tamaño y formato pedidos."""
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.fixture
def garment_with_image(auth_client: TestClient) -> dict:
    """Prenda del catálogo con su imagen ya subida, lista para probarse."""
    created = auth_client.post(
        "/api/garments", json={"name": "Camisa de prueba", "category": "top"}
    )
    assert created.status_code == 201, created.text
    garment_id = created.json()["id"]

    uploaded = auth_client.post(
        f"/api/garments/{garment_id}/image",
        files={"file": ("camisa.png", make_image_bytes(200, 260, "crimson"), "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    return uploaded.json()
