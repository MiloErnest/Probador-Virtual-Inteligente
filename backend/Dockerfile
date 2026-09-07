# Imagen del backend (FastAPI + uvicorn).
#
# Multi-stage NO hace falta aquí: las dependencias son ruedas precompiladas
# (psycopg[binary], Pillow), no hay nada que compilar y separar etapas solo
# añadiría complejidad sin bajar el tamaño de forma apreciable.

FROM python:3.12-slim

# PYTHONDONTWRITEBYTECODE: no escribir .pyc en una capa que es de solo lectura
# en la práctica. PYTHONUNBUFFERED: que los logs salgan al momento y no se
# queden en un buffer, que en un contenedor equivale a no tener logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Las dependencias van ANTES que el código a propósito: Docker cachea por
# capas, y así cambiar un archivo .py no obliga a reinstalar todo pip.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# El contenedor no corre como root. Si alguien encuentra un fallo en la
# aplicación, se encuentra con un usuario sin privilegios.
RUN useradd --create-home --uid 1000 vfit \
    && mkdir -p /app/storage \
    && chown -R vfit:vfit /app
USER vfit

EXPOSE 8000

# `alembic upgrade head` antes de arrancar: el contenedor se responsabiliza de
# que el esquema esté al día. Es seguro repetirlo —si no hay migraciones
# pendientes no hace nada— y evita el fallo clásico de levantar la aplicación
# contra una base sin migrar.
#
# `exec` al final: uvicorn hereda el PID 1 y recibe las señales de parada, de
# modo que `docker compose down` lo cierra limpiamente en vez de matarlo.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
