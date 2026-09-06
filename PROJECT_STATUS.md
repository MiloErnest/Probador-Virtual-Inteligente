# Estado del proyecto

> Documento vivo. Se actualiza al cerrar cada etapa.

**Etapa actual:** 1 — Infraestructura base
**Última actualización:** 2026-09-06

---

## Funcionalidades terminadas

### Backend
- [x] Aplicación FastAPI con CORS configurado por entorno.
- [x] Configuración por variables de entorno (`pydantic-settings`), sin secretos en el código.
- [x] Conexión a PostgreSQL con SQLAlchemy 2.0 (síncrono).
- [x] Endpoint `GET /api/health` que informa también del estado de la base de datos.
- [x] Modelos `User`, `Garment`, `TryOnSession` con sus relaciones.
- [x] Creación automática de tablas al arrancar.
- [x] Registro de usuarios con contraseña cifrada (bcrypt) — `POST /api/users`.
- [x] Catálogo de prendas: listar, filtrar por categoría, obtener, crear.
- [x] Subida de imagen de prenda con validación de tipo y tamaño.
- [x] Costura de almacenamiento (`Storage`) con implementación en disco local.
- [x] Servido de archivos estáticos en `/media`.
- [x] Historial de pruebas (solo lectura) — `GET /api/try-on-sessions`.
- [x] Script de datos de ejemplo (`python -m scripts.seed`), idempotente.
- [x] 22 pruebas automatizadas sobre SQLite en memoria — **ejecutadas y en verde**.

### Frontend
- [x] React 18 + TypeScript + Vite + Tailwind, configurados a mano y con alias `@/`.
- [x] Rutas y layout con las 6 secciones del producto.
- [x] Cliente HTTP único con manejo de errores de FastAPI y de red.
- [x] Hook `useApi` con estados de carga, error y recarga.
- [x] Indicador de salud del backend en la barra superior.
- [x] Catálogo consumiendo datos reales, con filtro por categoría.
- [x] Historial de pruebas consumiendo el endpoint real.
- [x] Páginas de fases futuras con aviso explicativo en vez de enlaces muertos.
- [x] Diseño responsive (móvil, tablet, escritorio).

---

## Funcionalidades pendientes

### Etapa 2 (siguiente)
- [ ] **Migraciones con Alembic** — antes de que haya datos que no se puedan perder.
- [ ] **Autenticación JWT**: `POST /api/auth/login`, dependencia `get_current_user`,
      protección de endpoints y sesión en el frontend.
- [ ] Formularios de registro e inicio de sesión.
- [ ] Eliminar la muleta del "ID de usuario" en *Mis pruebas*.

### Fase 1 del MVP (probador funcional)
- [ ] Elegir proveedor de Virtual Try-On y definir el `Protocol` en `app/ai/`.
- [ ] `POST /api/try-on-sessions`: subir foto, invocar IA, guardar resultado.
- [ ] Procesamiento en segundo plano (empezar con `BackgroundTasks`, no con Celery).
- [ ] Pantalla del probador con subida de foto y selección de prenda.

### Fases 2–5
- [ ] Generación de diseños con lenguaje natural (Fase 2).
- [ ] Análisis corporal con MediaPipe y recomendación de talla (Fase 3).
- [ ] Visor 3D con Three.js / R3F, materiales PBR y telas (Fase 4).
- [ ] Realidad aumentada con cámara en vivo (Fase 5).

---

## Errores conocidos y limitaciones

| # | Descripción | Impacto | Plan |
|---|---|---|---|
| 1 | ~~Nada se ha ejecutado todavía.~~ **Backend verificado**: 22 pruebas en verde con Python 3.12.10. Falta ejecutar el frontend y la base de datos. | Medio | Pasos 6–8 de la verificación. |
| 1b | ~~El README encadenaba comandos con `&&`, que no existe en Windows PowerShell 5.1.~~ **Corregido**: un comando por bloque. | — | Resuelto. Entorno de referencia: Windows 11 + PowerShell 5.1. |
| 1c | ~~`CORS_ORIGINS` reventaba el arranque: pydantic-settings decodifica los campos complejos como JSON antes de los validadores.~~ **Corregido** con `NoDecode` + 5 pruebas de regresión. | — | Resuelto. |
| 2 | **No hay autenticación.** Todos los endpoints son públicos. | Alto | Etapa 2. No exponer el backend fuera de `localhost` hasta entonces. |
| 3 | **Sin migraciones.** `create_all` solo crea tablas nuevas; no aplica cambios a tablas existentes. | Medio | Alembic al inicio de la Etapa 2. |
| 4 | Los tests usan SQLite, no PostgreSQL. No validan comportamiento específico de PG. | Medio | Aceptable mientras el esquema sea portable. |
| 5 | **El proyecto está dentro de OneDrive.** `node_modules` y `.venv` provocan sincronización constante, builds lentos y bloqueos de archivo. | Medio | Mover a `C:\dev\` o excluir esas carpetas de OneDrive. |
| 6 | El tipo de imagen se valida por la cabecera `Content-Type` que envía el cliente, no por el contenido real del archivo. | Bajo | Validar con Pillow cuando se acepten fotos de usuarios. |
| 7 | Las imágenes se sirven desde el proceso de FastAPI. | Bajo | Delegar en Nginx/CDN cuando haya despliegue real. |
| 8 | Sin límite de peticiones ni de tamaño total de subida por usuario. | Bajo | Antes de exponer la aplicación públicamente. |

---

## Decisiones técnicas

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| Monolito modular por capas | Microservicios | Con un dominio aún poco conocido, los límites de servicio se pondrían mal. Se extraerá el worker de IA cuando la lentitud lo justifique. |
| SQLAlchemy síncrono | `AsyncSession` | Consultas triviales; el modo síncrono es más simple de depurar y testear. FastAPI ya lo ejecuta en threadpool. |
| `create_all` en Etapa 1 | Alembic desde el inicio | Menos piezas para arrancar. Alembic entra en la Etapa 2, antes de que existan datos irrecuperables. |
| `image_key` en BD, `image_url` en la API | Guardar la URL completa | Migrar a S3/R2 no obliga a reescribir filas ya almacenadas. |
| Enums como `VARCHAR + CHECK` | `ENUM` nativo de PostgreSQL | Añadir un valor a un ENUM nativo exige `ALTER TYPE`; estas listas van a crecer. |
| `bcrypt` directo | `passlib[bcrypt]` | passlib 1.7.4 falla con bcrypt ≥ 4.1 y no tiene mantenimiento activo. |
| `max_length=72` en la contraseña | Sin límite | bcrypt trunca en silencio a 72 bytes; sin el límite, dos contraseñas distintas serían equivalentes. |
| `ondelete=RESTRICT` en `garment_id` | `CASCADE` | Borrar una prenda no debe destruir el historial del usuario. Se retira con `active = false`. |
| `fetch` nativo | axios | No aporta nada que necesitemos; una dependencia menos. |
| Hook `useApi` propio | TanStack Query | Aún no hay caché ni revalidación que gestionar. Se adoptará cuando exista la necesidad. |
| React 18 | React 19 | Todo el ecosistema (incluido React Three Fiber, que llega en Fase 4) es compatible sin fricción. |
| Tailwind v3 | Tailwind v4 | v4 cambia a configuración CSS-first; casi toda la documentación existente es de v3. |
| Un solo `tsconfig.json` | *Project references* (`tsconfig.node.json`) | Las referencias exigen `composite: true`, incompatible con `noEmit`. Su ventaja son las compilaciones incrementales en monorepos; aquí solo añadían una configuración rota. |
| PostgreSQL nativo con rol `vfit` dedicado | Usar el superusuario `postgres` | La aplicación no debe correr como superusuario, y así el `DATABASE_URL` es idéntico con instalación nativa o con Docker. |
| Docker solo para PostgreSQL | Dockerizar toda la aplicación | El hot-reload nativo es más rápido y más fácil de depurar en desarrollo. |
| `app/ai/` vacío, sin `Protocol` | Definir la interfaz ya | Una interfaz escrita antes de tener una implementación real casi siempre es la equivocada. |

---

## Verificación de la Etapa 1

Ejecutar en orden, **un comando por vez** (PowerShell 5.1 no admite `&&`).
Los pasos 1–4 no necesitan base de datos. La etapa está cerrada cuando los 9 pasan.

| # | Comprobación | Esperado | Estado |
|---|---|---|---|
| 1 | `python --version` | 3.12.x | ✅ 3.12.10 |
| 2 | venv activo (`python -c "import sys; print(sys.prefix)"`) | termina en `\backend\.venv` | ✅ |
| 3 | `pip install -r requirements-dev.txt` | sin errores | ✅ |
| 4 | `pytest` | 22 pruebas en verde | ✅ |
| 5 | PostgreSQL escuchando en 5432 | servicio activo | ✅ 16.15-3 |
| 6 | `python -m scripts.seed` | `Prendas creadas: 8` | ✅ 3 tablas, 8 filas |
| 7 | La app arranca contra PostgreSQL | sin excepciones | ✅ |
| 8 | `/api/health` | `"status":"ok"`, `"database":"up"` | ✅ |
| 9 | <http://localhost:5173/catalogo> | 8 prendas y el indicador dice **En línea** | ✅ |

**ETAPA 1 CERRADA.** Los 9 puntos verificados el 2026-09-06. El recorrido completo
React → `fetch` → FastAPI → SQLAlchemy → PostgreSQL funciona, incluido el filtro
por categoría. `npm run build` compila sin errores con TypeScript en modo estricto.

## Entorno local verificado

| Componente | Versión | Notas |
|---|---|---|
| Windows | 11 Pro | PowerShell 5.1 — **no admite `&&`** |
| Python | 3.12.10 | venv en `backend\.venv` |
| Node / npm | 24.19.0 / 11.17.0 | |
| PostgreSQL | 16.15-3 | Instalado con winget en modo silencioso |

**Base de datos local:** base `vfit`, rol `vfit` con contraseña `vfit_dev_password`
(las mismas credenciales que `docker-compose.yml`, para que el `DATABASE_URL` sea
idéntico con instalación nativa o con Docker).

> ⚠️ El superusuario `postgres` quedó con la contraseña por defecto `postgres`,
> que puso la instalación silenciosa de winget. Es aceptable en una base local
> que solo escucha en `localhost`, pero **cámbiala si este equipo llega a estar
> en una red compartida**:
> `ALTER USER postgres WITH PASSWORD 'otra-contrasena';`

---

## Próximo paso

**Etapa 2 — Autenticación y migraciones**, en este orden:

1. Alembic: migración inicial que refleje el esquema actual.
2. `POST /api/auth/login` con JWT y dependencia `get_current_user`.
3. Proteger `/api/users/{id}` y `/api/try-on-sessions`.
4. Formularios de registro y login en el frontend, con el token en memoria.
5. Retirar el campo manual de "ID de usuario" de *Mis pruebas*.

La Etapa 1 está cerrada y verificada, así que la Etapa 2 puede empezar.

> **Nota de continuidad:** cada etapa se desarrolla en una conversación nueva.
> Este documento y [CLAUDE.md](CLAUDE.md) son el único puente entre sesiones —
> mantenlos al día al cerrar cada etapa.
