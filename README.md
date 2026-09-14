# Probador Virtual

Un probador de ropa que funciona con la cámara del navegador. Eliges una prenda
del catálogo, te pones delante de la cámara y la prenda se coloca sobre tu
cuerpo, ajustada a tus medidas. Proyecto universitario.

**No usa ninguna IA generativa.** La detección del cuerpo es MediaPipe Pose
compilado a WebAssembly y corre entera en tu navegador: la imagen de la cámara
no sale de tu equipo. El backend solo sirve el catálogo, las cuentas y las
fotografías de las prendas.

**Estado actual: funciona de punta a punta.**
Ver [PROJECT_STATUS.md](PROJECT_STATUS.md) para el detalle de lo que funciona y
lo que falta.

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
el esquema se crea solo. No hace falta ninguna cuenta externa ni ninguna clave:
el proyecto no llama a ningun servicio de terceros.

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

| Ruta | Que hace | Acceso |
|---|---|---|
| `/` | Portada: que hace la aplicacion y hasta donde llega | Publica |
| `/catalogo` | Prendas disponibles, filtro por categoria | Publica |
| `/probador` | Camara + prenda superpuesta y ajustada a tu cuerpo | Requiere cuenta |
| `/entrar`, `/registro` | Acceso y alta | Publicas |
| `/perfil` | Tu cuenta y estado del sistema | Requiere cuenta |

Desde el catalogo, cada prenda enlaza al probador con ella ya elegida
(`/probador?prenda=12`).

**La API entera son cuatro recursos:**

| Endpoint | Que hace | Acceso |
|---|---|---|
| `GET /api/health` | Estado del servicio y de la base de datos | Publico |
| `GET /api/garments` | Catalogo, con filtro por categoria | Publico |
| `GET /api/garments/{id}` | Una prenda | Publico |
| `POST /api/garments` | Alta de prenda | Token |
| `POST /api/garments/{id}/image` | Subir o reemplazar su fotografia | Token |
| `POST /api/users` | Registro | Publico |
| `GET /api/users/{id}` | Tu cuenta (la de otro responde 404) | Token |
| `POST /api/auth/login` | Iniciar sesion, devuelve un JWT | Publico |
| `GET /api/auth/me` | Quien soy segun el token | Token |

---

## 6g. Como se coloca la prenda

Es la parte con matematica, y vive entera en `frontend/src/probador/`.

1. **MediaPipe Pose** devuelve, por fotograma, 33 puntos del cuerpo y una
   mascara que dice que pixeles son la persona.
2. **`cuerpo.ts`** convierte esos puntos en medidas. Aplica la correccion
   anatomica: los puntos del modelo estan en la ARTICULACION del hombro, por
   dentro del cuerpo, no en su borde exterior.
3. **`vestir.ts`** decide donde va la prenda (segun su categoria), cuanto mide
   de ancho (igualando su franja de ajuste al cuerpo) y como se deforma: se
   parte en 28 franjas horizontales y cada una sigue el eje del cuerpo.
4. El **tejido** decide cuanto se cine la prenda al contorno real. Un cuero
   mantiene su forma; un punto fino se pega.

**Lo que NO hace:** simular la tela. No hay pliegues, ni sombras propias, ni
peso, ni oclusion (si pones la mano delante del pecho, la prenda te la tapa).
Es una vista previa de corte y proporcion.

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
    probador/     El probador: cámara, medidas del cuerpo y encaje
```

El probador es el único sitio con algo de complejidad, y está partido en
cuatro archivos con una responsabilidad cada uno:

```
probador/
  usePoseScanner.ts    Cámara + MediaPipe. Devuelve puntos y silueta.
  cuerpo.ts            Medidas del cuerpo, suavizado y contorno real.
  vestir.ts            Dónde va la prenda, cuánto mide, cómo se deforma.
  dibujo.ts            Silueta, esqueleto y máscara de recorte.
  removeBackground.ts  Recorta el fondo de la foto de producto.
```

El flujo de una petición es siempre el mismo:

```
Ruta (HTTP) → Servicio (negocio) → Repositorio (SQL) → Modelo
```

Las rutas no ejecutan SQL, los repositorios no lanzan errores HTTP y los servicios
no conocen FastAPI.

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
