# Contexto del proyecto

Léeme antes de tocar nada. Recoge decisiones y restricciones que no son
evidentes leyendo el código, y evita repetir errores ya cometidos.

**Qué es:** un probador de ropa que funciona con la cámara del navegador.
Eliges una prenda del catálogo, te pones delante de la cámara y la prenda se
coloca sobre tu cuerpo, ajustada a tus medidas. Proyecto universitario.

**Estado:** funciona de punta a punta y **no usa ninguna IA generativa**. La
detección del cuerpo es MediaPipe Pose corriendo en WebAssembly dentro del
navegador; el backend solo sirve el catálogo, las cuentas y las imágenes.

**El 2026-09-14 se retiró toda la IA generativa del proyecto.** Fuera el
probador por foto con Gemini, el generador de diseños por texto y el análisis
corporal, con sus tablas, sus rutas y sus pantallas. Estaba construido y
funcionaba, pero con proveedores simulados: producía vistas previas que no
convencían, y el problema real —que la prenda no encajaba bien sobre el
cuerpo— seguía sin resolverse porque el esfuerzo se repartía entre cinco
fases. Ahora el proyecto hace una cosa.

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

**Nota para el asistente:** los heredocs de Bash con archivos largos (más de
unos pocos KB) se rompen en este entorno con `unexpected EOF while looking for
matching quote`, y el archivo no llega a crearse. Para archivos grandes, usa la
herramienta de escritura directa. Los heredocs cortos sí funcionan, y el UTF-8
sobrevive: los acentos van bien.

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
memoria — **no necesitan PostgreSQL levantado**. Son 53 y tardan unos 24 s;
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

Cargar el catálogo de ejemplo con las fotografías reales del repositorio:

```powershell
python -m scripts.seed --con-prendas-reales
```

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
12. **No reintroducir IA generativa** sin que el usuario lo pida. Se retiró a
    conciencia el 2026-09-14. Si vuelve, vuelve como decisión suya.

**Verificar antes de afirmar.** Nada se da por funcionando hasta ejecutarlo. En
la Etapa 1, tres bugs (`CORS_ORIGINS`, `tsconfig` con project references, y el
`.gitignore` de `storage/`) solo aparecieron al ejecutar de verdad.

**Nunca escribir contraseñas en un formulario, ni siquiera las de desarrollo.**
Para revisar una pantalla protegida, el asistente abre la ruta temporalmente
fuera de `RequireAuth`, hace la captura y la devuelve a su sitio comprobándolo
después. Así se verifica el diseño sin tocar credenciales.

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
- `app/api/deps.py::get_current_user` — **único** punto que convierte un token en
  un usuario. Declararlo en una ruta es lo que la protege. Ninguna ruta debe
  decodificar un token por su cuenta.

### El probador vive entero en el navegador

`frontend/src/probador/`, cuatro módulos con una responsabilidad cada uno:

| Archivo | Qué hace |
|---|---|
| `usePoseScanner.ts` | Abre la cámara y ejecuta MediaPipe Pose. Devuelve 33 puntos del cuerpo y la máscara de silueta, por fotograma. |
| `cuerpo.ts` | Convierte esos puntos en medidas de pantalla, las suaviza entre fotogramas y mide el contorno real sobre la máscara. |
| `vestir.ts` | Decide dónde va la prenda, cuánto mide y cómo se deforma. Es donde está la matemática del encaje. |
| `dibujo.ts` | Silueta, esqueleto y la máscara engordada con la que se recorta la prenda. |

**Las tres decisiones que gobiernan el encaje**, y el orden importa:

1. **Dónde empieza y acaba la prenda** — lo dice su categoría (`TRAMOS` en
   `vestir.ts`). Una camiseta cuelga de los hombros; un pantalón, de la cintura.
2. **Dónde se mide para escalarla** — la franja donde esa prenda *ajusta*
   (`referencia`). Fue el primer error de esta versión: escalando por el punto
   más ancho, el tamaño de una camiseta lo decidían las mangas, y salía pequeña
   y corta. Un pantalón ajusta en la cadera, un vestido en el cuerpo, una
   camiseta en el torso por debajo de las mangas.
3. **Cuánto manda el cuerpo frente a la forma de la prenda** — lo dice el
   tejido (`TEJIDOS`). Es el único efecto que tiene hoy el campo `fabric`.

Dos límites que hay que respetar al tocar esto:

- **Los puntos de MediaPipe NO son el borde del cuerpo.** Están en la
  articulación, por dentro. `cuerpo.ts` aplica la corrección anatómica
  (`HOMBROS_A_ANCHO_REAL`, `CADERAS_A_ANCHO_REAL`). Sin ella, la prenda sale
  estrecha y aparece la tentación de compensarlo con un número a ojo, que es
  exactamente lo que hacía la versión anterior con un `1.9` que había que
  reajustar por cada foto y cada persona.
- **La máscara corrige la silueta, no decide el tamaño.** Con los brazos
  pegados al cuerpo, el barrido los incluye; con un fondo complicado, se rompe.
  Por eso la corrección está limitada (`CORRECCION_MINIMA` / `CORRECCION_MAXIMA`).

**Cómo verificar el encaje sin cámara:** en la consola del navegador se importa
`/src/probador/vestir.ts` con Vite, se construye una prenda sintética y un
cuerpo sintético, y se miden los píxeles que pinta. Es como se comprobó que una
camiseta acaba justo por debajo de la cadera y un pantalón llega al tobillo.
Está en PROJECT_STATUS.md con los números.

---

## Estado por partes

| Parte | Estado |
|---|---|
| Infraestructura: catálogo, usuarios, almacenamiento | ✅ |
| Alembic + autenticación JWT | ✅ |
| Probador con cámara: pose, medidas y encaje | ✅ |
| Tejido de la prenda (`fabric`) como ajuste de silueta | ✅ básico |
| Simulación real de telas y caída (3D) | ⬜ futuro |
| Acceso con Google | ⬜ futuro, lo pidió el usuario |

**Alembic fue antes que JWT** por una razón concreta: ya había datos reales en
PostgreSQL, y `create_all` no aplica cambios a tablas existentes — falla en
silencio y parece que funcionó.

### Reparto de acceso vigente

Públicos: `/api/health`, el catálogo en lectura, `POST /api/users` (registro) y
`POST /api/auth/login`. Todo lo demás exige `Authorization: Bearer <token>`.

El probador exige sesión aunque no envíe nada al servidor. **Es una decisión
del usuario, tomada el 2026-09-14**: quiere controlar el flujo de usuarios, y
más adelante entrar con Google. No abrirlo sin que lo pida.

Tres reglas que hay que mantener al añadir endpoints:

1. **El usuario sale del token, nunca de un parámetro.** El historial aceptaba
   `?user_id=` y eso permitía leer el de cualquiera cambiando un número.
2. **Un recurso ajeno responde 404, no 403.** Un 403 confirma que existe.
3. **Los fallos de identificación son indistinguibles entre sí**: mismo 401,
   mismo mensaje, y mismo tiempo de respuesta (por eso se verifica contra un
   hash señuelo cuando el email no existe).

---

## Diseño de la interfaz

Blanco y negro, sin color de acento. **No es una preferencia estética, es un
arreglo:** la versión anterior tenía violeta sobre fondo crema y el usuario la
describió como "muy pálida". El problema no era la falta de color, era el
contraste bajo en toda la página —fondo crema, texto gris— que dejaba todo a
media luz. La solución fue usar los extremos.

- Los grises son opacidades de la tinta (`ink-80`, `ink-60`…), nunca colores
  nuevos: así ninguno se desvía hacia el azul o el verde por accidente.
- **Los estados no se distinguen por color.** Un error usa peso y estructura;
  el indicador de salud usa forma (punto lleno, hueco, latiendo) y la palabra.
  Es lo único que funciona para quien no distingue el rojo del verde.
- Tipografía fluida con `clamp()`: un titular no cambia de tamaño de golpe al
  girar el móvil.
- El menú móvil ocupa la pantalla entera. Cuatro enlaces apretados contra el
  borde superior son cuatro objetivos pequeños.
