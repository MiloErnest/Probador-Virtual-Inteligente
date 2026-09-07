# Estado del proyecto

> Documento vivo. Se actualiza al cerrar cada etapa.

**Etapa actual:** 2 — Migraciones y autenticación (cerrada)
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

### Etapa 2 — Migraciones y autenticación
- [x] Alembic instalado y configurado; la URL sale de `DATABASE_URL`, no del `.ini`.
- [x] Migración inicial que reproduce el esquema de la Etapa 1, generada contra
      una base vacía desechable y verificada en las dos direcciones.
- [x] La base `vfit` de desarrollo marcada con `alembic stamp head`, con sus datos intactos.
- [x] `create_all` retirado del arranque: el esquema lo gobierna Alembic.
      La aplicación informa de la revisión aplicada al arrancar.
- [x] `POST /api/auth/login` con JWT (PyJWT, HS256) y `GET /api/auth/me`.
- [x] Dependencia `get_current_user`: único punto que convierte token en usuario.
- [x] Endpoints protegidos; `GET /api/users` eliminado y `?user_id=` retirado del historial.
- [x] Sin enumeración de cuentas: mismo 401 y mismo tiempo de respuesta, y 404 (no 403)
      en recursos ajenos.
- [x] La aplicación se niega a arrancar en producción con la `SECRET_KEY` de ejemplo.
- [x] Sesión en el frontend: `AuthContext`, formularios de acceso y registro,
      rutas protegidas y retirada del campo manual "ID de usuario".
- [x] 54 pruebas automatizadas — **ejecutadas y en verde**.

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

### Fase 1 del MVP (probador funcional) — siguiente
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
| 2 | ~~No hay autenticación. Todos los endpoints son públicos.~~ **Resuelto en la Etapa 2**: JWT, `get_current_user` y reparto de acceso verificado con 54 pruebas. | — | Resuelto. |
| 3 | ~~Sin migraciones.~~ **Resuelto en la Etapa 2**: Alembic gobierna el esquema; `create_all` ya no corre al arrancar. | — | Resuelto. |
| 4 | Los tests usan SQLite, no PostgreSQL. No validan comportamiento específico de PG. | Medio | Aceptable mientras el esquema sea portable. |
| 5 | **El proyecto está dentro de OneDrive.** `node_modules` y `.venv` provocan sincronización constante, builds lentos y bloqueos de archivo. | Medio | Mover a `C:\dev\` o excluir esas carpetas de OneDrive. |
| 6 | El tipo de imagen se valida por la cabecera `Content-Type` que envía el cliente, no por el contenido real del archivo. | Bajo | Validar con Pillow cuando se acepten fotos de usuarios. |
| 7 | Las imágenes se sirven desde el proceso de FastAPI. | Bajo | Delegar en Nginx/CDN cuando haya despliegue real. |
| 8 | Sin límite de peticiones ni de tamaño total de subida por usuario. **Incluye el login**: nada impide probar contraseñas en bucle. | Medio | Antes de exponer la aplicación públicamente. `slowapi` o un límite en el proxy. |
| 9 | **Sin refresh token ni lista de revocación.** Cerrar sesión descarta el token en el navegador, pero seguiría siendo válido hasta caducar (12 h). Cambiar `SECRET_KEY` es hoy la única forma de invalidar todas las sesiones. | Bajo | Solo si aparece la necesidad real de expulsar a alguien al momento. |
| 10 | **El token se guarda en `localStorage`.** Un fallo de XSS permitiría leerlo; una cookie `httpOnly` no. Se aceptó a cambio de que recargar no cierre la sesión, y porque la alternativa exige manejar CSRF y cookies entre orígenes. | Medio | Primer punto a revisar antes de un despliegue público. |
| 11 | **Cualquier usuario registrado puede dar de alta prendas.** No existe la distinción usuario/administrador. | Bajo | Columna `is_admin` cuando haya un panel que la justifique. |
| 12 | **Las migraciones no se ejecutan en los tests**, que siguen creando el esquema desde los modelos con SQLite. Los tests validan los modelos, no las migraciones. | Medio | Se contrastan a mano con `alembic check` (ver verificación de la Etapa 2). Una base PostgreSQL de test cuando el esquema se complique. |
| 14 | **El registro no verifica que el buzón exista.** Cualquier correo con forma válida crea una cuenta: no hay correo de confirmación ni columna `is_verified`. Se comprobó el 2026-09-06: el login SÍ rechaza correos inexistentes y contraseñas erróneas (401 en ambos); el agujero está solo en el alta. | Medio | Se resolverá con el acceso mediante Google, que garantiza el buzón de paso. Ver «Próximo paso». |
| 13 | La suite tarda ~15 s (antes 1,4 s). Es bcrypt, que es lento a propósito, multiplicado por los registros e inicios de sesión de las pruebas. | Bajo | Aceptable. Si molesta, bajar el coste de bcrypt solo en el entorno de test. |

---

## Decisiones técnicas

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| Monolito modular por capas | Microservicios | Con un dominio aún poco conocido, los límites de servicio se pondrían mal. Se extraerá el worker de IA cuando la lentitud lo justifique. |
| SQLAlchemy síncrono | `AsyncSession` | Consultas triviales; el modo síncrono es más simple de depurar y testear. FastAPI ya lo ejecuta en threadpool. |
| `create_all` en Etapa 1 | Alembic desde el inicio | Menos piezas para arrancar. Alembic entró en la Etapa 2, antes de que existieran datos irrecuperables. |
| Migración inicial generada contra una base vacía desechable | Autogenerar contra `vfit` | Autogenerate compara los modelos con la base apuntada. Contra `vfit`, que ya tenía las tablas, habría producido una migración VACÍA y nos habríamos quedado sin migración fundacional. |
| `alembic stamp head` sobre `vfit` | Borrar y recrear la base | Había datos reales (8 prendas). Y una migración que solo funciona sobre una base vacía no sirve para lo que se creó. |
| `create_all` fuera del arranque | Dejarlo "por si acaso" | Dos fuentes de verdad para el esquema divergen en silencio: es exactamente el fallo que motivó poner Alembic antes que JWT. |
| `compare_type` y `compare_server_default` activos | Los valores por defecto de Alembic | Sin ellos, autogenerate se pierde los cambios de tipo, que son los más habituales. Tienen fama de falsos positivos, así que se comprobó contra el esquema real: `alembic check` sale limpio con ambos. |
| `PyJWT` | `python-jose` | Es lo que usa la documentación antigua de FastAPI, pero tiene mantenimiento irregular e historial de CVEs. PyJWT es Python puro y sin dependencias pesadas. |
| HS256 fijado en código | Algoritmo configurable por entorno | Un algoritmo elegido por configuración se puede degradar a `none`, y entonces cualquier token sin firma se acepta. |
| Login con JSON | `OAuth2PasswordRequestForm` | El formulario regala el botón Authorize de `/docs`, pero obliga a enviar un campo `username` que en realidad contiene un email, y a que el frontend trate el login como caso especial. Con `HTTPBearer` el botón sigue estando, pegando el token. |
| Token en `localStorage` | Solo en memoria; cookie `httpOnly` | En memoria, cada recarga cierra la sesión. La cookie es más segura pero exige CSRF y cookies entre orígenes. Riesgo asumido y anotado como limitación #10. |
| Validar el token guardado contra `/auth/me` al arrancar | Confiar en él | Un token caducado pintaría la interfaz como "sesión iniciada" con todas las peticiones fallando. |
| Releer el usuario en cada petición | Confiar en los datos del token | Es una consulta por clave primaria, y a cambio desactivar una cuenta corta el acceso al momento sin esperar a que caduque el token. |
| 404 en recursos ajenos | 403 | Un 403 confirma que el recurso existe: recorrer identificadores permitiría contar cuentas y pruebas. |
| Sin `POST /auth/logout` | Endpoint de cierre de sesión | Sin lista de revocación no podría invalidar nada: sería un endpoint que finge trabajar. |
| `GET /api/users` eliminado | Protegerlo con token | Devolvía todos los usuarios con sus correos, no tenía consumidor y no existe la figura de administrador que lo justifique. |
| **Seguir siendo aplicación web** | Empaquetar en un `.exe`/instalador | Se planteó el 2026-09-06 y **el usuario lo descartó: no es necesario**. Queda anotado porque la alternativa tenía consecuencias grandes: un instalador obliga a abandonar PostgreSQL (es un servicio aparte, no se empaqueta) y expondría cualquier clave de API dentro del ejecutable. Al descartarlo, PostgreSQL se queda y la arquitectura actual no necesita ningún cambio. **No reabrir sin que el usuario lo pida.** |
| Sin `is_admin` para dar de alta prendas | Añadir roles ya | Regla 10: infraestructura solo cuando haya necesidad demostrada. Anotado como limitación #11. |
| `image_key` en BD, `image_url` en la API | Guardar la URL completa | Migrar a S3/R2 no obliga a reescribir filas ya almacenadas. |
| Enums como `VARCHAR` **sin CHECK** | `ENUM` nativo de PostgreSQL | Añadir un valor a un ENUM nativo exige `ALTER TYPE`; estas listas van a crecer. **Corrección de la Etapa 2:** este documento decía "VARCHAR + CHECK". Era falso: desde SQLAlchemy 1.4, `Enum(native_enum=False)` tiene `create_constraint=False` por defecto, y se comprobó que no existe ninguna CHECK ni en la base ni en el DDL generado. Se deja así a propósito: una CHECK devolvería el mismo coste de migración que se quería evitar. Los valores los valida Pydantic en la entrada. |
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

## Verificación de la Etapa 2

Ejecutada el 2026-09-06. Todos los puntos comprobados de verdad, no por lectura
del código.

### Migraciones

| # | Comprobación | Resultado |
|---|---|---|
| 1 | Base vacía → `alembic upgrade head` | ✅ esquema creado |
| 2 | Esquema migrado vs. el que producía `create_all` | ✅ idénticos: 25 columnas, 9 índices, 5 constraints |
| 3 | `alembic check` tras migrar | ✅ «No new upgrade operations detected» |
| 4 | `alembic downgrade base` | ✅ limpio, solo queda `alembic_version` |
| 5 | `alembic stamp head` sobre `vfit` | ✅ revisión `d49edc91e56b`, 8 prendas intactas |
| 6 | `alembic check` sobre `vfit` | ✅ sin cambios pendientes |
| 7 | `python -m scripts.seed` tras migrar | ✅ `creadas: 0 | ya existentes: 8` |
| 8 | Arranque de la aplicación | ✅ registra «Base de datos en la revisión d49edc91e56b» |

### Autenticación (backend)

| # | Comprobación | Resultado |
|---|---|---|
| 9 | `pytest` | ✅ 54 pruebas en verde (antes 22) |
| 10 | Registro y login contra PostgreSQL real | ✅ token con `expires_in` = 43200 s |
| 11 | Contraseña incorrecta y email inexistente | ✅ mismo 401 y mismo mensaje |
| 12 | Login con el email en mayúsculas | ✅ 200 |
| 13 | Los 6 endpoints protegidos sin token | ✅ 401 en todos |
| 14 | Cuenta ajena / prueba ajena | ✅ 404, no 403 |
| 15 | `GET /api/users` | ✅ ya no existe (405) |
| 16 | Catálogo y `/api/health` sin token | ✅ públicos, 8 prendas |
| 17 | Token caducado, manipulado, de otro tipo o de usuario borrado | ✅ 401 en todos los casos |
| 18 | Cuenta desactivada con token todavía válido | ✅ pierde el acceso al momento |
| 19 | `ENVIRONMENT=production` con la `SECRET_KEY` de ejemplo | ✅ la aplicación no arranca |

### Sesión (frontend, en el navegador)

| # | Comprobación | Resultado |
|---|---|---|
| 20 | Catálogo sin cuenta | ✅ visible; «Mis pruebas» y «Perfil» ocultos |
| 21 | `/mis-pruebas` sin sesión | ✅ redirige a `/entrar` |
| 22 | Login con contraseña incorrecta | ✅ muestra el error genérico del backend |
| 23 | Login correcto | ✅ lleva a la página que se intentaba abrir |
| 24 | Recargar la página | ✅ la sesión sobrevive (`localStorage` + validación con `/auth/me`) |
| 25 | Token manipulado en `localStorage` | ✅ se descarta, se borra y vuelve al formulario |
| 26 | Registro desde la interfaz | ✅ crea la cuenta e inicia sesión |
| 27 | Cerrar sesión | ✅ borra el token y vuelve a la portada |
| 28 | Campo manual «ID de usuario» | ✅ eliminado |
| 29 | Móvil (375 px) | ✅ formularios y menú correctos |
| 30 | `npm run build` | ✅ compila con TypeScript estricto |

**ETAPA 2 CERRADA.**

---

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

**Fase 1 del MVP — el probador virtual funcionando**, en este orden:

1. Elegir proveedor de Virtual Try-On y **definir entonces** el `Protocol` de
   `app/ai/`, no antes: una interfaz escrita sin una implementación real casi
   siempre es la equivocada.
2. Migración para lo que el flujo real necesite (probablemente nada nuevo: la
   tabla `try_on_sessions` ya tiene estado, error y proveedor).
3. `POST /api/try-on-sessions`: subir foto, invocar a la IA, guardar resultado.
   Procesamiento con `BackgroundTasks`, **no** con Celery.
4. Pantalla del probador con subida de foto y selección de prenda.
5. Sondeo del estado en el frontend mientras la prueba está en `processing`.

Ya hay dos cosas resueltas que la Fase 1 daba por hechas: el usuario sale del
token (no hay que preguntar de quién es la prueba) y cambiar el esquema es
seguro (Alembic).

Punto a decidir al empezar: el proveedor de IA. La elección condiciona el
`Protocol`, el coste y si hace falta o no una cola de verdad.

### Después de la Fase 1

**Acceso con Google (OAuth).** Aplazado a propósito, no olvidado. Es aditivo, no
toca el núcleo, y resuelve de paso la limitación #14: Google ya garantiza que el
buzón existe y es de quien dice. Al haber descartado el instalador, el flujo es
el sencillo (redirección web), no el de escritorio.

Alternativa si Google se complica: verificación por correo con token de
confirmación e `is_verified`. Más piezas, y necesita una cuenta de correo
saliente.

> **Nota de continuidad:** cada etapa se desarrolla en una conversación nueva.
> Este documento y [CLAUDE.md](CLAUDE.md) son el único puente entre sesiones —
> mantenlos al día al cerrar cada etapa.
