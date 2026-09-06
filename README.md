# Probador Virtual Inteligente

Plataforma de prueba virtual de prendas con IA generativa, visión por computador,
modelado 3D y realidad aumentada. Proyecto universitario desarrollado por fases.

**Estado actual: Etapa 1 — Infraestructura base.**
Ver [PROJECT_STATUS.md](PROJECT_STATUS.md) para el detalle de lo que funciona y lo que falta.

---

> ### ⚠️ Antes de copiar comandos
>
> Este proyecto se desarrolla en **Windows PowerShell 5.1**, donde el operador `&&`
> **no existe** (`El token '&&' no es un separador de instrucciones válido`).
> Por eso en este documento **cada comando va por separado**: ejecútalos de uno en
> uno y comprueba que cada uno termina bien antes de pasar al siguiente.
>
> Si prefieres poder encadenar comandos con `&&`, instala PowerShell 7:
> `winget install Microsoft.PowerShell` y usa la terminal «PowerShell 7».

---

## 1. Instalar las herramientas

Ninguna de estas viene con Windows. Instálalas de una en una:

```powershell
winget install Python.Python.3.12
```

```powershell
winget install OpenJS.NodeJS.LTS
```

**Cierra y vuelve a abrir la terminal** después de instalar (el `PATH` no se
actualiza en las ventanas ya abiertas).

> **Si al escribir `python` se abre la Microsoft Store:** desactiva el alias en
> *Configuración → Aplicaciones → Configuración avanzada de aplicaciones →
> Alias de ejecución de aplicaciones*, y apaga las entradas `python.exe` y
> `python3.exe`.

Comprueba que todo responde:

```powershell
python --version; node --version; npm --version
```

Debe imprimir tres versiones. Si alguna falla, no sigas: soluciónala primero.

---

## 2. Base de datos

Elige **una** de las dos opciones.

### Opción A — PostgreSQL nativo (menos pasos)

```powershell
winget install PostgreSQL.PostgreSQL.16
```

El instalador pedirá una contraseña para el usuario `postgres`. **Apúntala.**
Después, crea la base de datos del proyecto:

```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -c "CREATE DATABASE vfit;"
```

Y ajusta esta línea en `backend\.env` con tu contraseña:

```
DATABASE_URL=postgresql+psycopg://postgres:TU_PASSWORD@localhost:5432/vfit
```

### Opción B — Docker (más reproducible, instalación más pesada)

Requiere WSL2, virtualización activada en la BIOS y un reinicio.

```powershell
winget install Docker.DockerDesktop
```

Reinicia, abre Docker Desktop una vez para que termine de configurarse, y luego:

```powershell
docker compose up -d
```

Levanta PostgreSQL en `localhost:5432` y Adminer en <http://localhost:8080>
(Servidor: `db` · Usuario: `vfit` · Contraseña: `vfit_dev_password` · Base: `vfit`).
Con esta opción el `DATABASE_URL` por defecto de `.env.example` ya es correcto.

---

## 3. Backend

Sitúate en la carpeta:

```powershell
cd backend
```

Crea el entorno virtual:

```powershell
python -m venv .venv
```

Actívalo:

```powershell
.venv\Scripts\Activate.ps1
```

> Si PowerShell bloquea el script («no se puede cargar porque la ejecución de
> scripts está deshabilitada»), ejecuta esto una sola vez y vuelve a intentarlo:
>
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

Sabrás que funcionó porque el prompt empieza por `(.venv)`.

Instala las dependencias:

```powershell
pip install -r requirements-dev.txt
```

Crea tu archivo de configuración:

```powershell
Copy-Item .env.example .env
```

Genera una clave secreta y pégala en `SECRET_KEY` dentro de `.env`:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Crea las tablas y carga el catálogo de ejemplo:

```powershell
python -m scripts.seed
```

Debe imprimir `Prendas creadas: 8 | ya existentes: 0`.

Arranca el servidor:

```powershell
uvicorn app.main:app --reload
```

- API: <http://localhost:8000>
- Documentación interactiva: <http://localhost:8000/docs>
- Salud: <http://localhost:8000/api/health>

**Deja esta terminal abierta.** El servidor se queda ejecutándose.

---

## 4. Frontend

Abre una **segunda terminal** (la del backend sigue ocupada).

```powershell
cd frontend
```

```powershell
npm install
```

```powershell
Copy-Item .env.example .env
```

```powershell
npm run dev
```

Aplicación: <http://localhost:5173>

---

## 5. Pruebas

En una terminal con el entorno virtual activado y dentro de `backend`:

```powershell
pytest
```

Los tests usan SQLite en memoria: **no necesitan PostgreSQL ni Docker levantados.**

Verificación de tipos del frontend (dentro de `frontend`):

```powershell
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

---

## 8. Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `El token '&&' no es un separador de instrucciones válido` | PowerShell 5.1 no soporta `&&` | Ejecuta los comandos de uno en uno, o instala PowerShell 7 |
| Al escribir `python` se abre la Microsoft Store | Alias de ejecución de Windows | Desactívalo en Configuración (ver sección 1) |
| `.venv\Scripts\Activate.ps1` no se puede cargar | Política de ejecución de scripts | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |
| `/api/health` responde `"database":"down"` | PostgreSQL no está levantado o el `DATABASE_URL` es incorrecto | Revisa la sección 2 y el `.env` |
| El frontend muestra «Sin conexión» | El backend no está corriendo | Arranca `uvicorn` en la otra terminal |
| `npm install` muy lento o con errores de permisos | El proyecto está dentro de OneDrive | Mueve el proyecto a `C:\dev\` |
