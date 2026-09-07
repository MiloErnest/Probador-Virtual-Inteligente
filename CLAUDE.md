# Contexto del proyecto

Léeme antes de tocar nada. Recoge decisiones y restricciones que no son
evidentes leyendo el código, y evita repetir errores ya cometidos.

**Qué es:** plataforma de prueba virtual de prendas con IA generativa, visión por
computador, 3D y realidad aumentada. Proyecto universitario, desarrollo por fases.

**Estado:** Etapas 1 (infraestructura) y 2 (migraciones + autenticación) cerradas
y verificadas. **Fase 1 en curso:** la tubería del probador funciona de punta a
punta (subir foto → encolar → procesar → mostrar), pero el proveedor actual es
una composición local con Pillow, **no IA**. Falta conectar el modelo real.

Ver [PROJECT_STATUS.md](PROJECT_STATUS.md) para el detalle vivo: qué funciona,
qué falta, errores conocidos, decisiones técnicas y próximos pasos.

---

## Entorno de desarrollo — restricciones reales

Estas cuatro cosas han roto comandos repetidamente. No son hipotéticas.

**1. Windows PowerShell 5.1. El operador `&&` NO existe.**
Falla con `El token '&&' no es un separador de instrucciones válido`. Escribe
**un comando por bloque**. Para encadenar usa `;` (siempre) o `; if ($?) { ... }`
(condicional).

**2. Las terminales heredan un `PATH` obsoleto.**
Una terminal abierta antes de instalar una herramienta no la ve, aunque la
instalación haya ido bien. El error dice "no se reconoce como nombre de cmdlet"
y parece que falta el programa. Para recargarlo:

```powershell
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
```

**3. Nunca asumas la carpeta actual.**
Un `cd backend` estando ya dentro de `backend` falla con
`No se encuentra la ruta de acceso ...\backend\backend`. Usa `Set-Location` con
ruta absoluta, o los scripts de arranque.

**4. El proyecto vive dentro de OneDrive.**
`node_modules` y `.venv` provocan sincronización. No ha dado problemas todavía,
pero es sospechoso número uno ante builds lentos o bloqueos de archivo.

### Arrancar el proyecto

```powershell
.\start-backend.ps1
```

```powershell
.\start-frontend.ps1
```

Resuelven el `PATH` y las rutas solos, funcionan desde cualquier carpeta y no
requieren activar el entorno virtual.

### Versiones instaladas y verificadas

Python 3.12.10 · Node 24.19.0 / npm 11.17.0 · PostgreSQL 16.15-3 · gh 2.100.0
(instalado, **sin autenticar**)

### Base de datos local

Base `vfit`, rol de aplicación `vfit` / `vfit_dev_password`. Son las mismas
credenciales que `docker-compose.yml`, a propósito: el `DATABASE_URL` sirve igual
con PostgreSQL nativo o con Docker. El superusuario `postgres` quedó con la
contraseña por defecto `postgres` (instalación silenciosa de winget).

Ejecutar pruebas: `pytest` desde `backend/` con el venv activo. Usan SQLite en
memoria — **no necesitan PostgreSQL levantado**. Son 54 y tardan unos 15 s;
la lentitud es bcrypt, que es lento a propósito.

**El esquema lo gobierna Alembic, no `create_all`.** La aplicación ya no crea
tablas al arrancar. Sobre una base nueva:

```powershell
alembic upgrade head
```

Tras tocar cualquier archivo de `app/models/`, comprobar si hace falta migración:

```powershell
alembic check
```

Y si la hace:

```powershell
alembic revision --autogenerate -m "descripcion"
```

Revisa siempre el archivo generado. Autogenerate ve tablas y columnas, no
intenciones: lo que para él es "columna nueva" puede ser un renombrado que debe
conservar los datos.

Cuenta de desarrollo ya creada en la base local: `dev@example.com` /
`vfit-dev-1234`.

---

## Cómo trabajar

**Git: commits directos a `main`. NO abrir pull requests.**
El usuario lo eligió explícitamente: trabaja solo y los PR sin revisor solo
añaden ceremonia. Hay dos remotos, ambos suyos:

```powershell
git push                      # origin  (claudeplus09)
```

```powershell
git push institucion main     # institucion (MiloErnest)
```

**Un chat por etapa.** Cada etapa del proyecto se desarrolla en una conversación
nueva. Por eso este archivo y `PROJECT_STATUS.md` tienen que quedar siempre al
día: son el único puente entre sesiones.

**Reglas que pidió el usuario:**

1. Trabajar por etapas pequeñas; cada una deja el sistema ejecutable.
2. Explicar qué se va a construir y por qué **antes** de crear archivos.
3. No inventar APIs, endpoints ni librerías. Verificar que existen.
4. Al añadir una dependencia: nombre, versión, instalación, propósito y riesgos
   de compatibilidad.
5. Ante varias alternativas: comparar brevemente y elegir una.
6. No sustituir algo que funciona por una arquitectura más compleja sin motivo.
7. Secretos siempre por variables de entorno.
8. Archivos completos y ejecutables, no fragmentos.
9. Mantener al día en `PROJECT_STATUS.md`: terminado, pendiente, errores
   conocidos, decisiones y próximos pasos.
10. **Es una aplicación web, no se empaqueta en un ejecutable.** Se planteó el
    2026-09-06 y el usuario lo descartó. Implicación: PostgreSQL se queda como
    base de datos. No proponer SQLite, PyInstaller, Electron ni Tauri salvo que
    el usuario lo pida.
11. **No añadir infraestructura "por si acaso"** (Redis, Celery, Kubernetes,
    microservicios, S3, pgvector, GPU serverless). Solo cuando exista una
    necesidad concreta y demostrada.

**Verificar antes de afirmar.** Nada se da por funcionando hasta ejecutarlo. En
la Etapa 1, tres bugs (`CORS_ORIGINS`, `tsconfig` con project references, y el
`.gitignore` de `storage/`) solo aparecieron al ejecutar de verdad.

---

## Arquitectura

Monolito modular. Una app FastAPI, un proceso, una base de datos.

```
Ruta (HTTP) → Servicio (negocio) → Repositorio (SQL) → Modelo
```

- Las rutas no ejecutan SQL. Solo llaman a servicios.
- Los repositorios no conocen HTTP ni lanzan `HTTPException`.
- Los servicios no conocen FastAPI. Lanzan errores de dominio
  (`app/services/exceptions.py`) que las rutas traducen a códigos HTTP.

**Costuras deliberadas** (puntos preparados para cambiar de implementación):

- `app/services/storage.py` — protocolo `Storage`. La BD guarda `image_key`
  (clave opaca), la API expone `image_url`. Migrar a S3/R2 no obliga a reescribir
  datos.
- `app/ai/` — `TryOnProvider` (protocolo) y `LocalPreviewProvider`, que compone
  la prenda sobre la foto con Pillow y **no es IA**. Conectar el modelo real es
  escribir una clase mas y anadir una rama en `get_try_on_provider()`. El
  protocolo es joven: solo lo cumple una implementacion, asi que cuenta con
  tener que ajustarlo al escribir la segunda.
- `app/api/deps.py::get_current_user` — **único** punto que convierte un token en
  un usuario. Declararlo en una ruta es lo que la protege. Ninguna ruta debe
  decodificar un token por su cuenta.
- `app/vision/` — reservado para la Fase 3 (MediaPipe). No instalar sus
  dependencias hasta que haya código que las use; irán en un
  `requirements-vision.txt` aparte.

---

## Fases del proyecto

| Fase | Contenido | Estado |
|---|---|---|
| Etapa 1 | Infraestructura: catálogo, usuarios, almacenamiento | ✅ cerrada |
| Etapa 2 | Alembic + autenticación JWT | ✅ cerrada |
| Fase 1 | Virtual Try-On con IA (foto + prenda → resultado) | 🟡 tuberia lista, falta el modelo |
| Fase 2 | Generación de diseños por lenguaje natural | ⬜ |
| Fase 3 | Análisis corporal, pose, medidas, talla | ⬜ |
| Fase 4 | 3D, Three.js / R3F, materiales PBR, telas | ⬜ |
| Fase 5 | Realidad aumentada, cámara en vivo, oclusión | ⬜ |

**Alembic fue antes que JWT** por una razón concreta: ya había datos reales en
PostgreSQL, y `create_all` no aplica cambios a tablas existentes — falla en
silencio y parece que funcionó.

### Reparto de acceso vigente (Etapa 2)

Públicos: `/api/health`, el catálogo en lectura, `POST /api/users` (registro) y
`POST /api/auth/login`. Todo lo demás exige `Authorization: Bearer <token>`.

Tres reglas que hay que mantener al añadir endpoints:

1. **El usuario sale del token, nunca de un parámetro.** El historial aceptaba
   `?user_id=` y eso permitía leer el de cualquiera cambiando un número.
2. **Un recurso ajeno responde 404, no 403.** Un 403 confirma que existe.
3. **Los fallos de identificación son indistinguibles entre sí**: mismo 401,
   mismo mensaje, y mismo tiempo de respuesta (por eso se verifica contra un
   hash señuelo cuando el email no existe).
