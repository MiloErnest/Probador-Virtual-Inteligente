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

### Refrescar el PATH después de instalar

Windows fija el `PATH` cuando arranca un proceso: **los programas ya abiertos
siguen viendo el PATH antiguo**, aunque la instalación haya ido bien. Por eso
justo después de instalar algo suele aparecer un
`El término 'python' no se reconoce...` aunque el programa exista.

La forma segura es **cerrar la aplicación entera** (el editor o terminal, no solo
la pestaña) y volver a abrirla. Si prefieres no cerrar nada, recarga el PATH en
la sesión actual:

```powershell
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
```

> **Si al escribir `python` se abre la Microsoft Store:** eso es el alias de
> Windows (un archivo de 0 bytes en `WindowsApps`). Ocurre cuando el Python real
> no está en el `PATH`, o está después del alias. Comprueba primero cuál se está
> usando:
>
> ```powershell
> Get-Command python -All | Select-Object -ExpandProperty Source
> ```
>
> Si el primero es `...\WindowsApps\python.exe`, desactiva el alias en
> *Configuración → Aplicaciones → Configuración avanzada de aplicaciones →
> Alias de ejecución de aplicaciones*, y apaga `python.exe` y `python3.exe`.

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

**Necesita una terminal como administrador**: pulsa Inicio → escribe `PowerShell`
→ clic derecho → *Ejecutar como administrador*. Sin elevar, la instalación se
cancela sola con `0x800704c7 : The operation was canceled by the user`.

Winget lo instala en **modo silencioso**: no verás ningún asistente y no te
pedirá contraseña. Deja el superusuario `postgres` con la contraseña por defecto,
que también es `postgres`, y registra un servicio de Windows que arranca solo con
el equipo.

Crea el rol y la base del proyecto (desde una terminal normal):

```powershell
$env:PGPASSWORD='postgres'; & "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -h localhost -d postgres -c "CREATE ROLE vfit LOGIN PASSWORD 'vfit_dev_password';"
```

```powershell
$env:PGPASSWORD='postgres'; & "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -h localhost -d postgres -c "CREATE DATABASE vfit OWNER vfit;"
```

Se usan **las mismas credenciales que `docker-compose.yml`** a propósito: así el
`DATABASE_URL` de `.env.example` funciona sin cambios tanto con PostgreSQL nativo
como con Docker. La aplicación se conecta con el rol `vfit`, nunca como
superusuario.

> ⚠️ La contraseña por defecto `postgres`/`postgres` es débil. Aceptable en una
> base local que solo escucha en `localhost`; cámbiala si el equipo llega a estar
> en una red compartida:
> `ALTER USER postgres WITH PASSWORD 'otra-contrasena';`

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

## 3. Arranque rápido (una vez completado el primer arranque)

Dos scripts en la raíz del proyecto se encargan de releer el `PATH`, resolver
las rutas y arrancar cada servicio. Funcionan **desde cualquier carpeta** y no
requieren activar el entorno virtual.

Terminal 1:

```powershell
.\start-backend.ps1
```

Terminal 2:

```powershell
.\start-frontend.ps1
```

El resto de esta sección describe el primer arranque paso a paso, y qué hacer
cuando algo falla.

---

## 4. Backend (primer arranque, paso a paso)

Sitúate en la carpeta. **Usa la ruta absoluta** si no estás seguro de dónde
estás: un `cd backend` cuando ya estás dentro de `backend` falla con
`No se encuentra la ruta de acceso ...\backend\backend`.

```powershell
Set-Location "C:\Users\camil\OneDrive\Desktop\Universidad\ClaudePoryectos\backend"
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

**Comprueba que el entorno está realmente activo antes de seguir.** El prefijo
`(.venv)` del prompt es fácil de pasar por alto, y si te equivocas aquí las
dependencias se instalan en el Python global sin avisar:

```powershell
python -c "import sys; print(sys.prefix)"
```

Debe terminar en `\backend\.venv`. Si en cambio imprime
`...\Programs\Python\Python312`, el entorno **no** está activo: no continúes
hasta resolverlo.

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

Crea las tablas aplicando las migraciones:

```powershell
alembic upgrade head
```

Es el único modo correcto de crear el esquema. La aplicación ya **no** crea
tablas al arrancar: `create_all` solo añade tablas nuevas y no aplica cambios a
las que ya tienen datos, así que un cambio de esquema se perdía en silencio.

Carga el catálogo de ejemplo:

```powershell
python -m scripts.seed
```

Debe imprimir `Prendas creadas: 8 | ya existentes: 0`. Si la base no está
migrada, el script se detiene y te lo dice en vez de fallar con un error de SQL.

Arranca el servidor:

```powershell
uvicorn app.main:app --reload
```

- API: <http://localhost:8000>
- Documentación interactiva: <http://localhost:8000/docs>
- Salud: <http://localhost:8000/api/health>

**Deja esta terminal abierta.** El servidor se queda ejecutándose.

---

## 5. Frontend (primer arranque, paso a paso)

Abre una **segunda terminal** (la del backend sigue ocupada).

```powershell
Set-Location "C:\Users\camil\OneDrive\Desktop\Universidad\ClaudePoryectos\frontend"
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

## 6. Pruebas

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

## 6b. Migraciones (Alembic)

Todos los comandos se ejecutan desde `backend/` con el entorno virtual activo.
La URL de la base sale de `DATABASE_URL`; no está escrita en `alembic.ini`.

Aplicar las migraciones pendientes:

```powershell
alembic upgrade head
```

Ver en qué revisión está la base:

```powershell
alembic current
```

Avisar si los modelos se han separado del esquema (útil tras tocar `app/models/`):

```powershell
alembic check
```

Generar una migración después de cambiar un modelo:

```powershell
alembic revision --autogenerate -m "descripcion del cambio"
```

**Revisa siempre el archivo generado antes de aplicarlo.** Autogenerate detecta
tablas, columnas, índices y tipos, pero no adivina intenciones: un `ALTER` que
para él es "columna nueva" puede ser en realidad un renombrado que debe
conservar los datos.

---

## 6c. Autenticación

Crear una cuenta:

```powershell
curl.exe -X POST http://localhost:8000/api/users -H "Content-Type: application/json" -d "{\"name\":\"Tu Nombre\",\"email\":\"tu@example.com\",\"password\":\"una-contrasena-larga\"}"
```

Obtener un token:

```powershell
curl.exe -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d "{\"email\":\"tu@example.com\",\"password\":\"una-contrasena-larga\"}"
```

Usarlo en `/docs`: botón **Authorize**, pegar el `access_token`.

Qué exige token y qué no:

| Endpoint | Acceso |
|---|---|
| `GET /api/health` | público |
| `GET /api/garments`, `GET /api/garments/{id}` | público |
| `POST /api/users` (registro) | público |
| `POST /api/auth/login` | público |
| `GET /api/auth/me` | token |
| `GET /api/users/{id}` | token, y solo tu propia cuenta |
| `GET /api/try-on-sessions` | token (el usuario sale del token) |
| `GET /api/try-on-sessions/{id}` | token, y solo tus pruebas |
| `POST /api/garments`, `POST /api/garments/{id}/image` | token |

El token dura 12 horas (`ACCESS_TOKEN_EXPIRE_MINUTES`). No hay refresh token ni
lista de revocación: cerrar sesión descarta el token en el navegador, pero
seguiría siendo válido hasta caducar.

---

## 6d. Conectar Gemini para la prueba virtual real

Por defecto el probador usa `AI_PROVIDER=local`, que **compone la prenda sobre
la foto con Pillow y no es IA**. Funciona sin cuenta, sin clave y sin conexion.

Para usar el modelo de verdad hacen falta cuatro pasos. **Los tres primeros son
tuyos**: implican crear una cuenta y activar un metodo de pago.

### 1. Crear la clave

Entra en <https://aistudio.google.com/apikey> con tu cuenta de Google y crea una
clave de API. Anotala; solo se muestra una vez.

### 2. Activar la facturacion

**El nivel gratuito de la API de Gemini NO incluye generacion de imagenes.** Sin
un metodo de pago asociado, las peticiones fallaran con un error de permisos.

En Google AI Studio, la clave pertenece a un proyecto de Google Cloud. Abre ese
proyecto en <https://console.cloud.google.com/billing> y asociale una cuenta de
facturacion.

### 3. Ponerle un limite de gasto

Hazlo antes de la primera prueba, no despues. Cada prueba virtual genera una
imagen y se cobra: del orden de unas centesimas de dolar con los modelos
`flash`. La aplicacion **no tiene limite de peticiones** (limitacion #8), asi
que nada impide que alguien lance pruebas en bucle.

En la consola de Google Cloud, dentro de Facturacion, crea un presupuesto con
alerta. Es la unica red de seguridad real que vas a tener.

### 4. Configurar el proyecto

Edita `backend/.env` (que esta en `.gitignore`, nunca se sube):

```
AI_PROVIDER=gemini
GEMINI_API_KEY=la-clave-que-acabas-de-crear
GEMINI_MODEL=gemini-3.1-flash-image
```

Reinicia el backend. En los registros vera la revision de la base y, a partir de
ahi, cada prueba usara el modelo. La columna `provider` de cada prueba guarda
cual la genero (`gemini:gemini-3.1-flash-image`), asi que el historial distingue
las hechas con IA de las hechas con la composicion local.

### Volver atras

Si se agota la cuota, el servicio falla o simplemente quieres dejar de gastar:

```
AI_PROVIDER=local
```

La aplicacion sigue funcionando de forma degradada en vez de romperse.

### Que esperar

- **Marca de agua.** Google incrusta una marca invisible (SynthID) en todo lo
  que genera. No se puede desactivar.
- **Bloqueos.** El modelo puede negarse a procesar ciertas fotografias por sus
  filtros de seguridad. La prueba quedara en `failed` con un mensaje que lo
  explica, no colgada.
- **Calidad.** Depende mucho de la foto: funciona mejor de cuerpo entero, de
  frente, bien iluminada y con fondo despejado.

---

## 6e. Todo con Docker

Por defecto, `docker compose up -d` levanta **solo PostgreSQL**, como siempre:
en desarrollo el hot-reload nativo es mas rapido y mas facil de depurar.

Para levantar la aplicacion entera en contenedores (base de datos, backend y
frontend), hay un perfil aparte:

```powershell
docker compose --profile full up -d --build
```

- Frontend: <http://localhost:3000>
- API: <http://localhost:8000>
- Adminer: <http://localhost:8080>

El puerto del frontend es 3000 y no 5173, a proposito: asi se puede tener a la
vez el servidor de desarrollo de Vite.

El contenedor del backend ejecuta `alembic upgrade head` al arrancar, asi que
el esquema se crea solo. Los proveedores van en modo simulado (`local` y
`mock`), o sea que funciona sin ninguna cuenta externa.

Para parar:

```powershell
docker compose --profile full down
```

> **Aviso: estas imagenes nunca se han construido.** Se escribieron con el
> demonio de Docker parado, asi que solo esta validada la sintaxis del
> `docker-compose.yml` y el funcionamiento de los perfiles. Los `Dockerfile`
> estan sin probar (limitacion #20 de PROJECT_STATUS.md). Si el primer
> `--build` falla, es esperable y hay que corregirlo.

---

## 6f. Que hace cada pantalla

| Ruta | Que hace | Estado del modelo |
|---|---|---|
| `/catalogo` | Prendas disponibles, filtro por categoria | Publico, sin IA |
| `/probador` | Foto + prenda (o diseno) -> resultado | **Simulado**: compone con Pillow |
| `/disenar` | Describe una prenda, generala, iterala | **Simulado**: siluetas por palabras clave |
| `/cuerpo` | Medidas a mano o por foto, y tu talla | Analisis **simulado**; el tallaje es real |
| `/mis-pruebas` | Historial de pruebas | - |
| `/perfil` | Tu cuenta y estado del sistema | - |

Las tres pantallas con modelo simulado lo advierten en un aviso visible. No se
presentan como IA.

**Endpoints anadidos en las Fases 2 y 3:**

| Endpoint | Que hace |
|---|---|
| `POST /api/designs` | Genera un diseno desde texto (202 + sondeo) |
| `POST /api/designs/{id}/refine` | Itera: crea una version nueva, no sobrescribe |
| `GET /api/designs` | Tus disenos |
| `GET /api/body-profile` | Tus medidas |
| `PUT /api/body-profile` | Crear o actualizar medidas (parcial) |
| `POST /api/body-profile/analyse` | Estimar medidas desde una foto |
| `DELETE /api/body-profile` | Borrar perfil y foto |
| `GET /api/body-profile/size-recommendation` | Tu talla, con el porque |

`POST /api/try-on-sessions` acepta ahora `garment_id` **o** `design_id`, nunca
los dos: es lo que conecta la Fase 2 con la Fase 1.

---

## 7. Estructura

```
backend/
  app/
    api/          Rutas HTTP y dependencias inyectables
    core/         Configuración, base de datos, seguridad
    models/       Tablas (SQLAlchemy)
    schemas/      Contratos de la API (Pydantic)
    repositories/ Acceso a datos
    services/     Lógica de negocio + almacenamiento de archivos
    ai/           Proveedores de prueba virtual (local y Gemini)
    vision/       Analisis corporal (protocolo + simulado)
  alembic/        Migraciones de esquema
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

## 8. Secretos

Ninguna clave vive en el código. Todo se lee de variables de entorno:

- `backend/.env` — configuración del servidor (queda fuera de git).
- `frontend/.env` — solo variables `VITE_*`, **que acaban visibles en el navegador**.
  Nunca pongas ahí claves de API.

Los archivos `.env.example` documentan cada variable y sí se versionan.

---

## 9. Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `El token '&&' no es un separador de instrucciones válido` | PowerShell 5.1 no soporta `&&` | Ejecuta los comandos de uno en uno, o instala PowerShell 7 |
| `El término 'python'` / `'npm' no se reconoce` **justo después de instalarlo** | El proceso arrancó antes de la instalación y conserva el `PATH` viejo | Cierra y reabre la aplicación entera, o usa `.\start-backend.ps1` / `.\start-frontend.ps1`, que releen el `PATH` solos |
| `No se encuentra la ruta de acceso ...\backend\backend` | Un `cd backend` ejecutado cuando ya estabas dentro de `backend` | Usa `Set-Location` con la ruta absoluta, o los scripts de arranque |
| `0x800704c7 : The operation was canceled by the user` al instalar con winget | El instalador pidió permisos de administrador y no se concedieron | Abre PowerShell **como administrador** y repite |
| Al escribir `python` se abre la Microsoft Store | Alias de ejecución de Windows por delante del Python real | Desactívalo en Configuración (ver sección 1) |
| `.venv\Scripts\Activate.ps1` no se puede cargar | Política de ejecución de scripts | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |
| `/api/health` responde `"database":"down"` | PostgreSQL no está levantado o el `DATABASE_URL` es incorrecto | Revisa la sección 2 y el `.env` |
| El frontend muestra «Sin conexión» | El backend no está corriendo | Arranca `uvicorn` en la otra terminal |
| Los paquetes se instalan en el Python global en vez de en `.venv` | El entorno virtual no estaba activado | Verifica con `python -c "import sys; print(sys.prefix)"` antes de instalar |
| `SettingsError: error parsing value for field "CORS_ORIGINS"` | Valor del `.env` con formato JSON en vez de separado por comas | Usa `CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173` |
| `npm install` muy lento o con errores de permisos | El proyecto está dentro de OneDrive | Mueve el proyecto a `C:\dev\` |
| Al arrancar: `La base de datos responde pero no tiene migraciones aplicadas` | Falta crear el esquema | `alembic upgrade head` desde `backend/` |
| `relation "users" does not exist` | Igual que el anterior | `alembic upgrade head` |
| `alembic` no se reconoce como comando | Instalado después de abrir la terminal, o entorno virtual sin activar | Reabre la terminal, o usa `.\start-backend.ps1` |
| Todas las peticiones responden 401 | El token caducó (12 h) o cambió `SECRET_KEY` | Vuelve a entrar en la aplicación |
| Al arrancar en producción: `SECRET_KEY sigue siendo un valor de ejemplo` | `ENVIRONMENT=production` con la clave del `.env.example` | Genera una real: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
