# Contexto del proyecto

Léeme antes de tocar nada. Recoge decisiones y restricciones que no son
evidentes leyendo el código, y evita repetir errores ya cometidos.

**Qué es:** plataforma de prueba virtual de prendas con IA generativa, visión por
computador, 3D y realidad aumentada. Proyecto universitario, desarrollo por fases.

**Estado:** Etapa 1 (infraestructura) cerrada y verificada. Ver
[PROJECT_STATUS.md](PROJECT_STATUS.md) para el detalle vivo: qué funciona, qué
falta, errores conocidos, decisiones técnicas y próximos pasos.

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
memoria — **no necesitan PostgreSQL levantado**.

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
10. **No añadir infraestructura "por si acaso"** (Redis, Celery, Kubernetes,
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
- `app/ai/` — **vacío a propósito**, reservado para la Fase 2. No definir el
  `Protocol` hasta tener una implementación real: una interfaz inventada antes de
  usarla suele ser la equivocada.
- `app/vision/` — reservado para la Fase 3 (MediaPipe). No instalar sus
  dependencias hasta que haya código que las use; irán en un
  `requirements-vision.txt` aparte.

---

## Fases del proyecto

| Fase | Contenido | Estado |
|---|---|---|
| Etapa 1 | Infraestructura: catálogo, usuarios, almacenamiento | ✅ cerrada |
| Etapa 2 | Alembic + autenticación JWT | ⬜ siguiente |
| Fase 1 | Virtual Try-On con IA (foto + prenda → resultado) | ⬜ |
| Fase 2 | Generación de diseños por lenguaje natural | ⬜ |
| Fase 3 | Análisis corporal, pose, medidas, talla | ⬜ |
| Fase 4 | 3D, Three.js / R3F, materiales PBR, telas | ⬜ |
| Fase 5 | Realidad aumentada, cámara en vivo, oclusión | ⬜ |

**Alembic va antes que JWT** por una razón concreta: ya hay datos reales en
PostgreSQL, y `create_all` no aplica cambios a tablas existentes — falla en
silencio y parece que funcionó.
