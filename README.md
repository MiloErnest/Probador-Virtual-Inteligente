# Probador Virtual Inteligente

Plataforma de prueba virtual de prendas con IA generativa, visión por computador,
modelado 3D y realidad aumentada. Proyecto universitario desarrollado por fases.

**Estado actual: Etapa 1 — Infraestructura base.**
Ver [PROJECT_STATUS.md](PROJECT_STATUS.md) para el detalle de lo que funciona y lo que falta.

---

## 1. Requisitos previos

| Herramienta | Versión | Instalación en Windows |
|---|---|---|
| Python | 3.12 | `winget install Python.Python.3.12` |
| Node.js | 22 LTS | `winget install OpenJS.NodeJS.LTS` |
| PostgreSQL | 16 | Docker (recomendado) o `winget install PostgreSQL.PostgreSQL.16` |
| Git | cualquiera | `winget install Git.Git` |

> **Windows:** si al escribir `python` se abre la Microsoft Store, desactiva el alias en
> *Configuración → Aplicaciones → Configuración avanzada de aplicaciones → Alias de ejecución*.
> Cierra y vuelve a abrir la terminal después de instalar cualquier herramienta.

Comprueba que todo esté disponible:

```bash
python --version && node --version && npm --version
```

---

## 2. Base de datos

### Opción A — Docker (recomendada)

```bash
docker compose up -d
```

Levanta PostgreSQL 16 en `localhost:5432` y Adminer en <http://localhost:8080>
(Servidor: `db` · Usuario: `vfit` · Contraseña: `vfit_dev_password` · Base: `vfit`).

### Opción B — PostgreSQL instalado nativamente

Crea la base y el usuario, y ajusta `DATABASE_URL` en `backend/.env`:

```sql
CREATE USER vfit WITH PASSWORD 'vfit_dev_password';
CREATE DATABASE vfit OWNER vfit;
```

---

## 3. Backend

```bash
cd backend
python -m venv .venv
```

Activar el entorno virtual:

```powershell
.venv\Scripts\Activate.ps1
```

> Si PowerShell bloquea el script:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

Instalar dependencias y configurar:

```bash
pip install -r requirements-dev.txt
```

```powershell
Copy-Item .env.example .env
```

Genera una `SECRET_KEY` propia y pégala en `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Cargar el catálogo de ejemplo (crea también las tablas):

```bash
python -m scripts.seed
```

Arrancar:

```bash
uvicorn app.main:app --reload
```

- API: <http://localhost:8000>
- Documentación interactiva: <http://localhost:8000/docs>
- Salud: <http://localhost:8000/api/health>

---

## 4. Frontend

En otra terminal:

```bash
cd frontend
npm install
```

```powershell
Copy-Item .env.example .env
```

```bash
npm run dev
```

Aplicación: <http://localhost:5173>

---

## 5. Pruebas

```bash
cd backend
pytest
```

Los tests usan SQLite en memoria: **no necesitan Docker ni PostgreSQL levantados.**

Verificación de tipos del frontend:

```bash
cd frontend
npm run typecheck
```

---

## 6. Estructura

```
backend/
  app/
    api/          Rutas HTTP y dependencias inyectables
    core/         Configuración, base de datos, seguridad
    models/       Tablas (SQLAlchemy)
    schemas/      Contratos de la API (Pydantic)
    repositories/ Acceso a datos
    services/     Lógica de negocio + almacenamiento de archivos
    ai/           RESERVADO — Fase 2
    vision/       RESERVADO — Fase 3
  scripts/        Utilidades (seed)
  storage/        Imágenes subidas (fuera de git)
  tests/

frontend/
  src/
    components/   Piezas de UI reutilizables
    layouts/      Estructura de página
    pages/        Una por sección de la navegación
    services/     Cliente HTTP y llamadas a la API
    hooks/        Lógica de React reutilizable
    types/        Espejo del contrato de la API
```

El flujo de una petición es siempre el mismo:

```
Ruta (HTTP) → Servicio (negocio) → Repositorio (SQL) → Modelo
```

Las rutas no ejecutan SQL, los repositorios no lanzan errores HTTP y los servicios
no conocen FastAPI. Esa separación es lo que permitirá extraer más adelante el
procesamiento de IA sin reescribir el resto.

---

## 7. Secretos

Ninguna clave vive en el código. Todo se lee de variables de entorno:

- `backend/.env` — configuración del servidor (queda fuera de git).
- `frontend/.env` — solo variables `VITE_*`, **que acaban visibles en el navegador**.
  Nunca pongas ahí claves de API.

Los archivos `.env.example` documentan cada variable y sí se versionan.
