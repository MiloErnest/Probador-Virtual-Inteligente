"""Configuración de pruebas.

DECISIÓN TÉCNICA
----------------
Los tests usan SQLite en memoria en lugar de PostgreSQL. Ventaja: `pytest`
funciona sin levantar Docker, cada test parte de una base limpia y la suite
tarda menos de un segundo.

Limitación conocida y aceptada: SQLite no es PostgreSQL. No se validan tipos
específicos de PG, constraints avanzadas ni comportamiento concurrente. Es
asumible mientras el esquema sea simple y portable (por eso los enums se
declaran con `native_enum=False`).

TAMBIÉN CONTRA POSTGRESQL (Ep2-Hu9)
-----------------------------------
Con la variable de entorno `TEST_DATABASE_URL` apuntando a una base
PostgreSQL, la suite corre contra ella:

    $env:TEST_DATABASE_URL = "postgresql+psycopg://vfit:vfit_dev_password@localhost:5432/vfit"
    pytest

Todo ocurre en un ESQUEMA propio, `pruebas_automaticas`, que se borra y se
rehace al empezar: los datos de `public` no se tocan, así que puede apuntar a
la base de desarrollo. Va en un esquema y no en una base aparte porque el rol
`vfit` no puede crear bases, y sí esquemas en la suya.

El esquema se construye con `alembic upgrade head`, no con `create_all`: así
la misma pasada comprueba que las migraciones dan el esquema que esperan los
modelos. Entre prueba y prueba se vacían las tablas (`TRUNCATE`), que es mucho
más rápido que rehacerlas.

El almacenamiento también se sustituye por un directorio temporal, de modo
que ningún test escriba en `backend/storage/`.
"""

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_sketch_runner, get_trial_runner, get_try_on_runner
from app.core.config import settings
from app.core.database import get_session
from app.main import app
from app.models import Base
from app.repositories.fabric import FabricRepository
from app.repositories.fabric_trial import FabricTrialRepository
from app.repositories.garment_upload import GarmentUploadRepository
from app.repositories.person_photo import PersonPhotoRepository
from app.repositories.try_on import TryOnRepository
from app.services.fabric_trial import FabricTrialService
from app.services.garment_upload import GarmentUploadService
from app.services.storage import LocalStorage, Storage, get_storage
from app.services.try_on import TryOnService
from app.textil import boceto_ia


@pytest.fixture(autouse=True)
def sin_gastar_dinero(monkeypatch):
    """Ninguna prueba llama nunca a una API de pago. Ni por accidente.

    Los tests leen el `.env` real, así que en cuanto alguien pone
    AI_PROVIDER=openai —que es lo normal cuando se está trabajando en esa
    parte— la suite entera empezaría a generar imágenes facturadas. Con una
    suite de setenta tests que se ejecuta decenas de veces al día, eso vacía
    una cuenta antes de que nadie entienda por qué.

    `autouse` es deliberado: esto no es algo que cada test deba acordarse de
    pedir. Un test que quiera probar el camino de la IA tiene que decirlo
    explícitamente, y aun así contra un cliente simulado.
    """
    monkeypatch.setattr(settings, "AI_PROVIDER", "none")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    # El probador es gratuito, pero llama a Hugging Face y gasta la cuota
    # diaria —dos pruebas sin cuenta—. Una suite que se ejecuta decenas de
    # veces al día la agotaría antes de que nadie la usara.
    monkeypatch.setattr(settings, "VTO_PROVIDER", "none")
    monkeypatch.setattr(settings, "HF_TOKEN", "")


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "").strip()

#: El esquema de PostgreSQL donde corren las pruebas. Se BORRA al empezar: no
#: puede ser `public`, donde están los datos de desarrollo.
ESQUEMA_DE_PRUEBAS = "pruebas_automaticas"


def _url_en_el_esquema(url: str) -> str:
    """La URL con el esquema de pruebas como `search_path`.

    Todo lo que se cree o se consulte sin esquema explícito va ahí, incluida
    la tabla de versiones de Alembic.
    """
    separador = "&" if "?" in url else "?"
    return f"{url}{separador}options=-csearch_path%3D{ESQUEMA_DE_PRUEBAS}"


@pytest.fixture(scope="session")
def motor_postgresql():
    """El motor de PostgreSQL, con el esquema recién migrado. Uno por sesión."""
    if not TEST_DATABASE_URL:
        yield None
        return
    if not TEST_DATABASE_URL.startswith("postgresql"):
        pytest.exit("TEST_DATABASE_URL tiene que ser una URL de PostgreSQL.", returncode=2)

    from alembic import command
    from alembic.config import Config

    base = create_engine(TEST_DATABASE_URL)
    with base.begin() as conexion:
        conexion.execute(text(f"DROP SCHEMA IF EXISTS {ESQUEMA_DE_PRUEBAS} CASCADE"))
        conexion.execute(text(f"CREATE SCHEMA {ESQUEMA_DE_PRUEBAS}"))
    base.dispose()

    # `alembic/env.py` lee la URL de `settings`, no de `alembic.ini`: se cambia
    # mientras dura la migración y se devuelve después.
    url = _url_en_el_esquema(TEST_DATABASE_URL)
    original = settings.DATABASE_URL
    settings.DATABASE_URL = url
    try:
        command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")
    finally:
        settings.DATABASE_URL = original

    motor = create_engine(url)
    yield motor
    motor.dispose()


@pytest.fixture
def engine(motor_postgresql):
    if motor_postgresql is not None:
        # Cada prueba parte de tablas vacías y de identificadores desde 1.
        tablas = ", ".join(t.name for t in Base.metadata.sorted_tables)
        with motor_postgresql.begin() as conexion:
            conexion.execute(text(f"TRUNCATE {tablas} RESTART IDENTITY CASCADE"))
        yield motor_postgresql
        return

    # StaticPool + una sola conexión: todas las sesiones comparten la misma
    # base en memoria (sin esto, cada conexión vería una base distinta).
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite trae las claves ajenas DESACTIVADAS por omisión, y hay que
    # encenderlas en cada conexión. Sin esto, los tests no comprueban ninguna
    # restricción de integridad: un borrado en cascada parece funcionar y en
    # PostgreSQL se comporta distinto. Se descubrió porque borrar una prenda
    # dejaba sus pruebas vivas solo en los tests.
    @event.listens_for(test_engine, "connect")
    def _activar_claves_ajenas(conexion, _registro):  # noqa: ANN001
        cursor = conexion.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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

    # La tarea de fondo real (`run_trial_job`) abre su PROPIA sesión con
    # `SessionLocal`, que apunta a PostgreSQL. Sin esta sustitución, crear una
    # prueba en un test escribiría en la base de desarrollo.
    #
    # TestClient ejecuta las tareas de fondo de forma SÍNCRONA al terminar la
    # petición, así que al volver de `client.post(...)` la prueba ya está
    # procesada. Cómodo para testear, distinto de producción: eso lo cubre la
    # verificación manual contra el servidor real.
    def procesar_prueba(trial_id: int) -> None:
        FabricTrialService(
            FabricTrialRepository(db_session),
            GarmentUploadRepository(db_session),
            FabricRepository(db_session),
            storage,
        ).process(trial_id)

    app.dependency_overrides[get_trial_runner] = lambda: procesar_prueba

    def procesar_prueba_sobre_persona(try_on_id: int) -> None:
        TryOnService(
            TryOnRepository(db_session),
            PersonPhotoRepository(db_session),
            FabricTrialRepository(db_session),
            GarmentUploadRepository(db_session),
            storage,
        ).process(try_on_id)

    app.dependency_overrides[get_try_on_runner] = lambda: procesar_prueba_sobre_persona

    def generar_prenda_de_boceto(upload_id: int) -> None:
        GarmentUploadService(
            GarmentUploadRepository(db_session),
            FabricTrialRepository(db_session),
            storage,
        ).generar(upload_id)

    app.dependency_overrides[get_sketch_runner] = lambda: generar_prenda_de_boceto

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# --- Autenticación -----------------------------------------------------------
#
# Casi todos los endpoints de escritura exigen un token. Estas utilidades
# evitan que cada prueba repita el registro y el login.

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


# --- Imágenes de prueba ------------------------------------------------------
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


def make_prenda_bytes(width: int = 300, height: int = 400) -> bytes:
    """Una «fotografía de prenda» sintética, con fondo liso y pliegues.

    Tiene que parecerse a una foto de producto en lo que le importa al motor:
    un fondo claro uniforme del que recortar, y un degradado dentro de la
    prenda que haga las veces de luz y sombra. Sin ese degradado, el
    retexturizado no tendría nada que reutilizar y la prueba no probaría nada.
    """
    from io import BytesIO

    from PIL import Image, ImageDraw

    imagen = Image.new("RGB", (width, height), (218, 218, 214))
    dibujo = ImageDraw.Draw(imagen)

    caja = (width // 5, height // 6, width * 4 // 5, height * 5 // 6)
    dibujo.rectangle(caja, fill=(120, 90, 70))

    # Un degradado vertical dentro de la prenda: es la «luz».
    for y in range(caja[1], caja[3]):
        t = (y - caja[1]) / max(1, caja[3] - caja[1])
        tono = int(70 + 90 * (1 - abs(t - 0.35) * 1.6))
        dibujo.line([(caja[0], y), (caja[2], y)], fill=(tono + 40, tono, tono - 20))

    buffer = BytesIO()
    imagen.save(buffer, format="PNG")
    return buffer.getvalue()


def make_boceto_bytes(width: int = 300, height: int = 400) -> bytes:
    """Un «boceto» sintético: papel blanco, contorno a lápiz y sombreado gris.

    La prenda ocupa la misma caja que la de `make_prenda_bytes`, para que la
    prenda que devuelve `GeneradorFalso` tenga su misma silueta.
    """
    from io import BytesIO

    from PIL import Image, ImageDraw

    imagen = Image.new("RGB", (width, height), (250, 250, 248))
    dibujo = ImageDraw.Draw(imagen)
    caja = (width // 5, height // 6, width * 4 // 5, height * 5 // 6)
    dibujo.rectangle(caja, fill=(226, 226, 224), outline=(40, 40, 40), width=3)

    buffer = BytesIO()
    imagen.save(buffer, format="PNG")
    return buffer.getvalue()


class GeneradorFalso:
    """Hace de modelo generativo sin llamar a nadie, y cuenta las llamadas.

    Devuelve lo que devuelve el de verdad: la prenda sola, en crudo, sobre
    gris. `caja` son las fracciones que ocupa; por defecto, las del boceto de
    `make_boceto_bytes`, que es «la prenda le ha salido fiel».
    """

    nombre = "falso-boceto"

    def __init__(self, caja: tuple[float, float, float, float] = (0.2, 1 / 6, 0.8, 5 / 6)):
        self.caja = caja
        self.llamadas = 0

    def generar(self, boceto, *, con_color: bool):
        from PIL import Image, ImageDraw

        self.llamadas += 1
        ancho, alto = 600, 800
        imagen = Image.new("RGB", (ancho, alto), (140, 140, 140))
        dibujo = ImageDraw.Draw(imagen)
        x0, y0 = round(self.caja[0] * ancho), round(self.caja[1] * alto)
        x1, y1 = round(self.caja[2] * ancho), round(self.caja[3] * alto)
        for y in range(y0, y1):
            t = (y - y0) / max(1, y1 - y0)
            tono = int(200 + 40 * (1 - abs(t - 0.35) * 1.6))
            dibujo.line([(x0, y), (x1, y)], fill=(tono, tono - 6, tono - 22))
        return boceto_ia.PrendaGenerada(imagen=imagen, proveedor=self.nombre, tokens=1234)


@pytest.fixture
def generador_de_bocetos(monkeypatch) -> GeneradorFalso:
    """Sustituye el modelo generativo por uno falso. Sin esto, un boceto falla
    diciendo que la IA no está configurada — que es lo que impone
    `sin_gastar_dinero`."""
    falso = GeneradorFalso()
    monkeypatch.setattr(boceto_ia, "generador_configurado", lambda: falso)
    return falso


@pytest.fixture
def fabric_with_texture(auth_client: TestClient) -> dict:
    """Tela del catálogo con su mosaico ya cargado, lista para probarse."""
    creada = auth_client.post(
        "/api/fabrics",
        json={
            "name": "Lino de prueba",
            "reference": "TEST-01",
            "composition": "100% lino",
            "weight_gsm": 190,
            "width_cm": 140,
            "price_per_meter": 16.5,
            "color_name": "Crudo",
            "color_hex": "#d6cab2",
            "pattern": "textured",
            "default_repeat": 7,
        },
    )
    assert creada.status_code == 201, creada.text

    subida = auth_client.post(
        f"/api/fabrics/{creada.json()['id']}/texture",
        files={"file": ("tela.png", make_image_bytes(64, 64, "tan"), "image/png")},
    )
    assert subida.status_code == 200, subida.text
    return subida.json()


@pytest.fixture
def uploaded_garment(auth_client: TestClient) -> dict:
    """Prenda subida por el usuario, con su recorte ya calculado."""
    respuesta = auth_client.post(
        "/api/garment-uploads",
        data={"name": "Camisa de prueba", "kind": "photo"},
        files={"file": ("camisa.png", make_prenda_bytes(), "image/png")},
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()
