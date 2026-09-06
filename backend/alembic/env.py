"""Entorno de ejecución de Alembic.

Dos decisiones importantes viven aquí:

1. **La URL se lee de `app.core.config.settings`, no de `alembic.ini`.**
   `alembic.ini` se versiona; poner ahí la contraseña de PostgreSQL sería
   filtrar un secreto al repositorio. Como efecto secundario, las migraciones
   apuntan siempre a la misma base que la aplicación, sin poder desincronizarse.

   Para migrar otra base sin tocar nada, exporta la variable de entorno:
       $env:DATABASE_URL = "postgresql+psycopg://..."   (PowerShell)

2. **`target_metadata` es el `Base.metadata` de la aplicación.** Se importa
   `app.models` completo (no `app.models.base`) porque el `__init__` es el que
   registra las tres tablas en los metadatos. Importar solo `Base` daría unos
   metadatos vacíos y autogenerate propondría BORRAR todas las tablas.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# `prepend_sys_path = .` en alembic.ini hace importable el paquete `app`
# cuando se ejecuta `alembic` desde la carpeta `backend/`.
from app.core.config import settings
from app.models import Base

config = context.config

# La URL no está en el .ini; se inyecta aquí en tiempo de ejecución.
# `escape_percent` evita que una contraseña con '%' rompa el parser de
# configparser, que interpreta '%' como inicio de una interpolación.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# Opciones comunes a los dos modos de ejecución.
#
# `compare_type`: detecta cambios de tipo de columna (VARCHAR(120) -> VARCHAR(200)).
#   Desactivado por defecto en Alembic, lo que hace que autogenerate se pierda
#   justo el tipo de cambio más habitual.
#
# `compare_server_default`: detecta cambios en los DEFAULT del servidor. Tiene
#   fama de generar falsos positivos, así que se ha comprobado contra el
#   esquema real de este proyecto (`alembic check` sale limpio con él activo).
#   Si algún día empieza a proponer diferencias fantasma en `created_at`,
#   ponlo a False: es una ayuda, no una garantía.
COMPARE_OPTIONS = {
    "compare_type": True,
    "compare_server_default": True,
}


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse a la base de datos (`alembic upgrade --sql`).

    Útil para revisar qué se va a ejecutar, o para entregar el SQL a alguien
    que administre la base y no quiera correr Python contra ella.
    """
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **COMPARE_OPTIONS,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica las migraciones conectándose a la base de datos."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            **COMPARE_OPTIONS,
        )

        # PostgreSQL soporta DDL transaccional: si una migración falla a mitad,
        # se deshace entera y la base no queda en un estado intermedio.
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
