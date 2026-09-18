# Contexto del proyecto

Léeme antes de tocar nada. Recoge decisiones y restricciones que no son
evidentes leyendo el código, y evita repetir errores ya cometidos.

**Qué es:** una plataforma web de **prueba virtual de telas**. Un diseñador,
una modista o un taller sube la fotografía de una prenda —o el boceto de una
que todavía no existe—, le prueba telas del catálogo y las compara lado a lado,
sin pedir muestras ni gastar metraje. Proyecto universitario.

El producto lo define el **Product Vision Board** que aportó el usuario
(`Product Vision Board - Probador Virtual de Telas.docx`). Sus cinco
características son el alcance: catálogo digital de telas, carga del boceto o
modelo, generación de la imagen con la tela aplicada, comparación lado a lado,
y galería e historial.

**El usuario del producto NO es quien se pone la ropa.** Es quien tiene que
elegir la tela. Eso invierte el catálogo: el catálogo es de **telas**, y las
prendas las pone el usuario.

**Funcionalidad adicional:** un probador con cámara que superpone prendas sobre
el cuerpo en vivo. Es de otra etapa, funciona, y se mantiene — pero no es el
producto y no aparece en el Vision Board.

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

### Versiones instaladas y verificadas

Python 3.12.10 · Node 24.19.0 / npm 11.17.0 · PostgreSQL 16.15-3 · gh 2.100.0
(instalado, **sin autenticar**)

### Base de datos local

Base `vfit`, rol de aplicación `vfit` / `vfit_dev_password`. Son las mismas
credenciales que `docker-compose.yml`, a propósito.

Ejecutar pruebas: `pytest` desde `backend/` con el venv activo. Usan SQLite en
memoria — **no necesitan PostgreSQL levantado**. Son 71 y tardan unos 35 s.

**El esquema lo gobierna Alembic, no `create_all`.** Sobre una base nueva:

```powershell
alembic upgrade head
```

Tras tocar cualquier archivo de `app/models/`, comprobar con `alembic check` y,
si hace falta, `alembic revision --autogenerate -m "descripcion"`. Revisa
siempre el archivo generado: autogenerate ve tablas y columnas, no intenciones.

Cuenta de desarrollo: `dev@example.com` / `vfit-dev-1234`.

Datos de ejemplo:

```powershell
python -m scripts.seed_telas
```

```powershell
python -m scripts.seed --con-prendas-reales
```

Y si `app/textil/segmentar.py` cambia, hay que recalcular los recortes ya
guardados — se calculan al subir y no se recalculan solos:

```powershell
python -m scripts.resegmentar --aplicar
```

El primero carga 12 telas con su ficha técnica y su mosaico. El segundo carga
el catálogo del probador con cámara.

---

## Cómo trabajar

**Git: commits directos a `main`. NO abrir pull requests.**

```powershell
git push                      # origin  (claudeplus09)
```

```powershell
git push institucion main     # institucion (MiloErnest)
```

**Un chat por etapa.** Por eso este archivo y `PROJECT_STATUS.md` tienen que
quedar siempre al día: son el único puente entre sesiones.

**Reglas que pidió el usuario:**

1. Trabajar por etapas pequeñas; cada una deja el sistema ejecutable.
2. Explicar qué se va a construir y por qué **antes** de crear archivos.
3. No inventar APIs, endpoints ni librerías. Verificar que existen.
4. Al añadir una dependencia: nombre, versión, instalación, propósito y riesgos.
5. Ante varias alternativas: comparar brevemente y elegir una.
6. No sustituir algo que funciona por una arquitectura más compleja sin motivo.
7. Secretos siempre por variables de entorno.
8. Archivos completos y ejecutables, no fragmentos.
9. Mantener al día `PROJECT_STATUS.md`.
10. **Es una aplicación web, no se empaqueta en un ejecutable.**
11. **No añadir infraestructura "por si acaso"** (Redis, Celery, Kubernetes,
    microservicios, S3). Solo con necesidad demostrada.

**Verificar antes de afirmar.** Nada se da por funcionando hasta ejecutarlo.

**Nunca escribir contraseñas en un formulario, ni siquiera las de desarrollo.**
Para revisar una pantalla protegida, abrir la ruta temporalmente fuera de
`RequireAuth`, hacer la captura y devolverla a su sitio comprobándolo después.

**Y nunca pegar la clave de API en el chat.** Ocurrió una vez y hubo que
revocarla. El código la lee de `OPENAI_API_KEY` en `backend/.env`, que está en
`.gitignore`; el asistente no necesita verla nunca.

---

## Arquitectura

Monolito modular. Una app FastAPI, un proceso, una base de datos.

```
Ruta (HTTP) → Servicio (negocio) → Repositorio (SQL) → Modelo
                    ↓
              app/textil/  (el motor, por debajo)
```

- Las rutas no ejecutan SQL. Solo llaman a servicios.
- Los repositorios no conocen HTTP ni lanzan `HTTPException`.
- Los servicios no conocen FastAPI. Lanzan errores de dominio
  (`app/services/exceptions.py`) que las rutas traducen a códigos HTTP.
- **El motor no conoce los servicios.** Lanza `ErrorDeMotor`
  (`app/textil/errores.py`) y el servicio lo traduce. Al principio lanzaba
  `ValidationError` directamente y eso creó un ciclo de importación que solo
  reventaba si algo importaba el motor antes que `app.main` — el ciclo era el
  síntoma; el problema era que una capa de abajo conocía la de arriba.

**Costuras deliberadas:**

- `app/services/storage.py` — protocolo `Storage`. La BD guarda claves opacas,
  la API expone URLs. Migrar a S3/R2 no obliga a reescribir datos.
- `app/api/deps.py::get_current_user` — **único** punto que convierte un token
  en un usuario.
- `app/textil/provider.py::motor_para` — **único** punto que decide qué motor
  corre.

### Dos catálogos, dos productos

| Tabla | Qué es |
|---|---|
| `fabrics` | El catálogo de la tienda textil. **El centro del producto.** |
| `garment_uploads` | La prenda o el boceto que sube el usuario. |
| `fabric_trials` | Una prueba: prenda × tela → imagen. La unidad de negocio. |
| `garments` | El catálogo del probador con cámara. Otra cosa, no se mezcla. |

---

## El motor textil — lo que hay que saber antes de tocarlo

`backend/app/textil/`. Es donde está la matemática y donde se han cometido y
corregido los errores más caros.

| Archivo | Qué hace |
|---|---|
| `segmentar.py` | Qué píxeles son prenda. Se calcula UNA vez al subir y se guarda. |
| `retexturizar.py` | El motor determinista: dos caminos, foto y boceto. |
| `filtros.py` | Desenfoque y reescalado en coma flotante. |
| `provider.py` | El contrato y el selector. |
| `openai_provider.py` | El motor generativo. |

### La idea, en una frase

Una fotografía ya contiene lo difícil: dónde hay un pliegue, dónde da la luz.
Esa información depende de la **forma**, no del color, así que se separa
dividiendo el brillo de cada píxel entre el brillo típico de la prenda — y lo
que queda se traslada a la tela nueva.

### Cinco cosas que costaron encontrarse

1. **Todo en coma flotante.** Pillow desenfoca en enteros de 0 a 255. Sobre una
   imagen no se nota; sobre un campo del que después se calcula el GRADIENTE es
   casi toda la señal. Síntoma: el estampado se troceaba en moaré. Y el mismo
   error se repitió al optimizar —cuantizando antes de ampliar— con el mismo
   resultado. **Regla: nunca cuantizar nada de lo que se vaya a derivar.**
2. **Multiplicar en luz lineal, no en sRGB.** Los valores de un PNG llevan una
   curva encima. Multiplicar sobre ellos no multiplica luz.
3. **El ruido se limpia en la DECISIÓN, no en el resultado.** El contorno
   dentado de la chaqueta se intentó arreglar con una apertura morfológica
   sobre la máscara ya hecha: funcionó en la chaqueta y **se comió el 7% de la
   camiseta blanca**, porque erosionar borra lo fino y lo fino era prenda.
   Suavizando el mapa de distancias antes de umbralizar, los picos desaparecen
   y la cobertura no se mueve ni una milésima.
4. **El cierre morfológico sella el túnel pero deja la cavidad.** Hace falta un
   segundo paso que rellene los huecos ya desconectados del borde.
5. **Un boceto SÍ tiene luz, y darlo por supuesto costó el motor entero.**
   Aquí ponía —escrito en el propio módulo— que un dibujo no tiene sombras. Es
   verdad de un plano técnico y falso del dibujo que de verdad hace un
   diseñador: un figurín va sombreado a lápiz, y ese sombreado es dónde caen
   los pliegues. El motor lo tiraba y lo sustituía por un degradado desde el
   borde; el usuario lo describió de una frase: «parece que le echara pintura a
   la prenda». Tenía razón, era relleno plano más viñeta.

   Lo que hay que separar en un dibujo no es forma contra color: es **trazo
   contra sombreado**, y lo que los distingue es la ANCHURA, no la oscuridad.
   Separarlos por oscuridad —que era lo que se hacía— mete la sombra cargada en
   el mismo saco que el contorno, y como el trazo se conserva tal cual, el
   dibujo entero seguía viéndose en gris por encima de la tela.

   Medido en el croquis de referencia: el rayado del lápiz hunde un 11% respecto
   al papel de al lado y el contorno un 73%. De ahí que el umbral sea doble
   (`PISO_DEL_TRAZO`, `PLENO_DEL_TRAZO`) y no simple: con uno solo, un tercio de
   la prenda se conservaba como tinta.
6. **En un croquis, el recorte se come a la modelo, y se distingue por
   saturación.** «Todo lo que no es fondo» incluye la cara, el pelo y los
   brazos, y la tela se los pintaba. El lápiz con el que se dibuja la prenda es
   acromático (saturación 0,02 de mediana) y la figura no (0,10+): hay un orden
   de magnitud, así que el umbral no es delicado. La regla clásica de tono de
   piel en RGB (Kovac) NO vale, está ajustada a fotografías y detectaba el 0,2%.

   Lleva una salvaguarda imprescindible: si lo detectado ocupa más del 30% del
   recorte, no es una persona, es una prenda de color cálido, y no se quita
   nada. Medido: el croquis da 0,05; la fotografía de la camiseta, 0,00.
7. **La máscara de OpenAI va al revés que la nuestra.** Ahí lo TRANSPARENTE es
   lo que se edita. Mandarla sin invertir da una imagen plausible y equivocada.

### Los parámetros están medidos, no elegidos a ojo

`DOBLADO_DEL_ESTAMPADO = 0.10`: a 0,06 se nota que la tela envuelve el hombro; a
0,20 aparecen remolinos; a 0,35 se derrite. `RADIO_CIERRE = 5`: con 3 queda una
ranura abierta en la camiseta blanca, y con 7 las perneras del vaquero siguen
separadas. Si cambias uno, mídelo igual.

---

## La IA: dónde está y por qué está ahí

**`AI_PROVIDER=openai`, modelo `gpt-image-1-mini`.** Se activa a conciencia; el
valor por defecto del repositorio es `none`, porque que clonarlo empiece a
gastar dinero de alguien sería una trampa. Un valor desconocido **hace fallar el
procesado**, nunca cae al motor local en silencio.

### Qué se le manda al modelo, que es la decisión que más pesa

**El retexturizado, no el original.** Una imagen que ya tiene el diseño del
usuario y ya tiene la tela puesta, pidiéndole solo que la haga fotográfica. La
primera versión mandaba el boceto crudo y pedía «un vestido de tafetán»: a eso
un modelo solo puede responder inventándose un vestido, y se lo inventaba.

**Y la salida se recompone contra el original a través de la máscara.**
`images.edit` **no** es un parcheo: regenera la imagen entera, también fuera de
la máscara. Por eso cambiaba el fondo aunque la máscara fuera perfecta. Con la
composición, todo lo que no es prenda —fondo, cara, pelo— queda idéntico al
original píxel a píxel. Es lo único que lo garantiza.

### Lo que se midió con llamadas reales

Cinco llamadas, dos prendas, los dos modelos. La conclusión no se movió.

| # | Motor | Partiendo de | Tiempo | Coste | Conserva el diseño |
|---|---|---|---|---|---|
| 1 | `gpt-image-1-mini` + fidelidad alta | boceto crudo | — | 0 | 400: el mini **no admite** el parámetro |
| 2 | `gpt-image-1-mini` | boceto crudo | 47 s | 7.880 | **No** — túnica lisa |
| 3 | `gpt-image-1` + fidelidad alta | boceto crudo | 46 s | 12.935 | **No** |
| 4 | `gpt-image-1-mini` | **retexturizado** | 24 s | 3.276 | **No** — manga larga y cuello barco |
| 5 | `gpt-image-1` + fidelidad alta | **retexturizado** | 52 s | 12.987 | **No** — igual |
| — | Retexturizado de boceto | — | 0,5 s | gratis | **Sí, entero** |

Las dos últimas son las importantes: **aunque se le dé la imagen ya hecha y solo
se le pida pulir, el modelo rediseña.** Con el modelo grande y con
`input_fidelity="high"`, que es el parámetro que existe justo para evitarlo.

Lo que sí resolvió el trabajo: de la 4 en adelante, el fondo, la cara y el pelo
son los del original y no los toca nadie. La composición funciona; lo que no se
puede es confiarle el interior de la prenda.

**Conclusión, y es una decisión de producto:** el camino por defecto es
siempre el determinista, también para bocetos. La IA es **opt-in** y sirve para
lo que sí sabe hacer —convertir un dibujo en algo fotorrealista— sabiendo que
reinterpreta el diseño y que se cobra.

Eso no debilita el uso de IA en el proyecto: lo justifica. Está donde aporta
algo que la otra vía no puede dar, y se elige a sabiendas.

### Control de gasto, en tres sitios

1. El límite mensual del panel de OpenAI. Lo puso el usuario.
2. `AI_TRIALS_PER_USER_PER_DAY` (20), ventana móvil de 24 h. Protege a unos
   usuarios de otros.
3. **Las pruebas automatizadas no pueden gastar nunca.** `conftest.py` tiene un
   fixture `autouse` que fuerza `AI_PROVIDER="none"`. Sin él, poner
   `AI_PROVIDER=openai` en el `.env` haría que la suite entera —71 tests,
   decenas de veces al día— generara imágenes facturadas.

La IA **se pide desde la pantalla de pruebas**, con un selector de motor. Antes
estaba integrada y era inalcanzable: el cliente aceptaba `method` y la pantalla
nunca lo mandaba, así que todo salía por el camino determinista.

**Sin reintentos automáticos**, con UNA excepción documentada: si la API rechaza
`input_fidelity` con un 400, se reintenta sin ese parámetro. Verificado contra
la API real: la petición que antes moría con ese 400 ahora sale adelante. Un 400 se rechaza
antes de generar imagen, así que no ha costado nada, y la alternativa —una lista
de qué modelo admite qué— caducaría con el siguiente modelo.

---

## Reparto de acceso

Públicos: `/api/health`, el catálogo de telas en lectura, el catálogo de
prendas del probador, `POST /api/users` y `POST /api/auth/login`. Todo lo demás
exige `Authorization: Bearer <token>`.

Tres reglas al añadir endpoints:

1. **El usuario sale del token, nunca de un parámetro.** El historial aceptaba
   `?user_id=` y eso permitía leer el de cualquiera cambiando un número.
2. **Un recurso ajeno responde 404, no 403.** Un 403 confirma que existe. Aquí
   importa más que en otros sitios: el boceto de un taller es su trabajo.
3. **Los fallos de identificación son indistinguibles entre sí**: mismo 401,
   mismo mensaje, mismo tiempo de respuesta.

---

## Diseño de la interfaz

Blanco y negro, sin color de acento. **No es preferencia estética, es un
arreglo:** la versión con violeta sobre crema se veía apagada por contraste
bajo en toda la página, no por falta de color.

- Los grises son opacidades de la tinta, nunca colores nuevos.
- **Los estados no se distinguen por color**, sino por forma y palabra. Es lo
  único que funciona para quien no distingue el rojo del verde.
- Tipografía fluida con `clamp()`.
- El menú móvil ocupa la pantalla entera.
