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

**El probador:** la otra pregunta, «¿cómo me queda a mí?». El usuario sube una
foto suya y se pone una prenda de SU taller —con la tela que eligió— en su
postura. Sustituyó en 2026-09-27 a un probador con cámara en vivo que tenía su
propio catálogo de ropa: el usuario pidió explícitamente que no fuera cámara, y
que no fuera un flujo aparte que duplicara el taller. Ver «El probador» abajo.

**Los bocetos:** el único sitio donde la IA generativa INVENTA. Un boceto no es
una prenda; la IA lo convierte, una vez, en la fotografía de la prenda, y sobre
ella se prueban las telas con el motor de siempre. Desde 2026-10-01 es una
pantalla aparte (`/bocetos`). Sustituyó al texturizado directo del dibujo, que
el usuario descartó: «un boceto con un color encima, nadie lo quiere». Ver
«Los bocetos» abajo.

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

Con un doble clic en **`Iniciar Probador.exe`**, en la raíz. Arranca los dos
servidores sin ventanas (salida en `logs/`), espera a que respondan, abre el
navegador, y al cerrar su ventana los apaga — también si se cierra con la X:
van dentro de un «job» de Windows que muere con él. Se compila, sin instalar
nada, con el compilador de C# que trae Windows:

```powershell
.\lanzador\compilar.ps1
```

El `.exe` no se versiona (binario sin firmar); su código, `lanzador/IniciarProbador.cs`,
sí. Y NO contradice la regla 10: no empaqueta la aplicación, solo la arranca.

A mano, en dos terminales:

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
memoria — **no necesitan PostgreSQL levantado**. Son 161: las del contrato de la
API; en `tests/test_motor.py`, las propiedades medidas del motor — cada una
es un caso que falló de verdad antes de arreglarse—; en `tests/test_mis_telas.py`,
una por criterio de aceptación de Ep6-Hu7 a Hu11; y en
`tests/test_probador.py`, la garantía del probador con un modelo que inventa
fondo, como el de verdad, y los defectos medidos el 10 y el 12/11/2026 con sus
salidas reales.

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

Y si `app/textil/segmentar.py` cambia, hay que recalcular los recortes ya
guardados — se calculan al subir y no se recalculan solos:

```powershell
python -m scripts.resegmentar --aplicar
```

Y si cambia `app/probador/conservar.py`, las pruebas sobre persona ya guardadas
se recomponen SIN llamar a Hugging Face ni gastar cuota (solo las que guardan
la salida del modelo: las hechas desde el 10/11/2026). Sin `--aplicar` dice
cuánto cambiaría cada una:

```powershell
python -m scripts.recomponer --aplicar
```

Y para que los mosaicos del catálogo sean fotográficos en vez de procedurales
(cuesta dinero, una vez por tela, y sin `--aplicar` solo dice lo que haría):

```powershell
python -m scripts.telas_fotograficas --aplicar
```

Las telas REALES de la tienda, sacadas de sus fotos (`scripts/muestras/`). Sin
`--con-ia` no cuesta nada; los dos estampados reconstruidos ya están en caché:

```powershell
python -m scripts.seed_telas_reales
```

El primero carga 12 telas de demostración con su ficha técnica y su mosaico.
Las prendas de ejemplo (`assets/prendas-de-ejemplo/`) se suben desde el taller
como cualquier otra; no hay script que las siembre.

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
10. **Es una aplicación web, no se empaqueta en un ejecutable.** El
    `Iniciar Probador.exe` que pidió el usuario no la empaqueta: solo arranca
    los dos servidores y abre el navegador.
11. **No añadir infraestructura "por si acaso"** (Redis, Celery, Kubernetes,
    microservicios, S3). Solo con necesidad demostrada.

**Verificar antes de afirmar.** Nada se da por funcionando hasta ejecutarlo.

**Nunca escribir contraseñas en un formulario, ni siquiera las de desarrollo.**
Para revisar una pantalla protegida, abrir la ruta temporalmente fuera de
`RequireAuth`, hacer la captura y devolverla a su sitio comprobándolo después.

**Y nunca pegar la clave de API en el chat.** Ocurrió una vez y hubo que
revocarla. El código la lee de `OPENAI_API_KEY` en `backend/.env`, que está en
`.gitignore`; el asistente no necesita verla nunca. Lo mismo con `HF_TOKEN`.

---

## Arquitectura

Monolito modular. Una app FastAPI, un proceso, una base de datos.

```
Ruta (HTTP) → Servicio (negocio) → Repositorio (SQL) → Modelo
                    ↓
     app/textil/  y  app/probador/  (los motores, por debajo)
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
- `app/probador/proveedor.py::modelo_configurado` — ídem para el modelo que
  viste a la persona.

### Las tablas

| Tabla | Qué es |
|---|---|
| `fabrics` | Las telas. **El centro del producto.** `owner_id` vacío: del catálogo de la tienda, público. Con valor: una tela que ese usuario fotografió en su taller, y solo la ve él (`/api/my-fabrics`). |
| `garment_uploads` | La prenda del usuario: una foto, o la que la IA generó de su boceto (el dibujo queda en `sketch_key`). Solo `status=ready` se puede probar. |
| `fabric_trials` | Una prueba: prenda × tela → imagen. La unidad de negocio. |
| `person_photos` | La foto de una persona. Sin metadatos; borrarla borra sus pruebas. |
| `try_ons` | Esa persona con una prenda del taller puesta. Guarda también lo que devolvió el modelo, sin componer. |

`garments` —el catálogo del probador con cámara— se eliminó en la migración
`32d71eca2214`, con la cámara.

---

## Los bocetos — lo que hay que saber antes de tocarlos

`backend/app/textil/boceto_ia.py`, `GarmentUploadService.generar` y
`frontend/src/pages/BocetosPage.tsx`.

```
boceto --[IA, UNA VEZ POR BOCETO, se cobra]--> fotografía de la prenda, sola,
                                               en su color o en crudo
prenda + máscara + mosaico --[determinista, SIEMPRE]--> la prenda con la tela
```

Subir un boceto responde con la prenda en `pending`; la generación corre en
segundo plano (`run_sketch_job`) y el cliente sondea. Las telas solo se pueden
probar con la prenda en `ready`.

### Lo que costó encontrar

1. **Esto ya se había intentado y había fallado**, y la diferencia no es el
   prompt. Antes se pedía «un vestido de tafetán»: imaginar la prenda e
   imaginar la tela a la vez, con un modelo que no admitía `input_fidelity`,
   una vez por cada tela y sin que nadie mirase el resultado. Ahora se pide
   SOLO la prenda, una vez, y el usuario la ve junto a su dibujo. Medido tres
   veces con el vestido de noche del usuario (palabra de honor con drapeado
   cruzado, sirena, sobrefalda con cola): las tres salieron con todo eso.
   Unos 3.400 tokens y 38 s cada una.
2. **No se puede prometer que sea idéntica.** `images.edit` interpreta el
   dibujo; no hay condicionamiento estructural. Por eso hay dos redes: el
   **parecido de silueta** (`parecido_de_silueta`, 0 a 1) y la comparación a
   ojo, con el dibujo y la prenda siempre lado a lado y un botón «Otra
   variante». El parecido mide el CONTORNO y nada de dentro: unos botones de
   más no lo mueven.
3. **`PARECIDO_MINIMO = 0.72` está medido.** Las prendas fieles del vestido dan
   0,87–0,88; contra siete prendas que no son la suya, 0,42–0,57.
4. **El recorte de la prenda generada no busca figura** (`figura=False`). El
   paso que quita a la modelo de un figurín tomaba por piel las sombras
   cálidas de los pliegues de una tela cruda, y dejaba dos agujeros de la
   cintura al bajo. **Se culpó primero al fondo gris** —«la sombra gris se
   confunde con el fondo gris»—, se montó un fondo azul de croma, y salieron
   LOS MISMOS agujeros. Se pagó una imagen por no medir antes de suponer.
5. **Si el boceto no tiene color, la prenda va en crudo**, y eso lo decide el
   código (`boceto_a_color`), no el modelo: dejándoselo a él, el sombreado
   gris del lápiz lo toma por un vestido gris.
6. **Cada variante es una prenda nueva.** No pisa la anterior: las telas ya
   probadas se hicieron sobre ELLA. Una prenda fallida sin pruebas se
   reintenta en su misma fila. Sin semilla: la API no la tiene, y cada
   llamada sale distinta sola.
7. **Los bocetos cuentan para `AI_TRIALS_PER_USER_PER_DAY`**, y el techo se
   comprueba ANTES de guardar el dibujo.
8. **Los bocetos subidos antes del cambio** quedaron en `failed` con un
   mensaje que dice qué hacer. La migración no los genera: cuesta dinero.
9. **Sin `AI_PROVIDER=openai`, un boceto falla diciendo cómo activarlo.** No
   hay camino gratuito al que caer en silencio.

---

## El probador — lo que hay que saber antes de tocarlo

`backend/app/probador/`. La foto de una persona con una prenda del taller.

| Archivo | Qué hace |
|---|---|
| `prenda.py` | Recorta la prenda del taller: los MISMOS píxeles de la prueba de tela. |
| `partes.py` | Analizador de personas (SegFormer B2 ropa, ONNX, CPU, 0,8 s). |
| `proveedor.py` | El contrato del modelo y el selector (`VTO_PROVIDER`). |
| `fashn.py` | FASHN VTON 1.5 en su Space gratuito de Hugging Face. |
| `conservar.py` | Qué se toma del modelo y qué vuelve a ser la foto original. El fondo, siempre el de la foto. |
| `vestir.py` | El camino: encuadrar según la prenda, vestir, conservar (`recomponer`, que no llama al modelo). |

### Lo que costó encontrar

1. **Se eligió FASHN VTON 1.5** entre los modelos abiertos con demo viva:
   Apache 2.0 (IDM-VTON y CatVTON son no comerciales; CatVTON estaba caído),
   pensado para conservar a la persona, genera en píxeles. Medido: persona
   sentada y persona frente a un espejo, prenda con su dibujo y su color, ~28 s.
2. **El modelo NO se limita a la prenda.** Regenera una caja alrededor del
   torso e inventa: en la foto del espejo cambió la ventana, un cuadro de la
   pared y los objetos del tocador, y añadió un cinturón. Por eso existe
   `conservar.py`: del resultado solo entra la ropa de la categoría (en la foto
   original Y en la generada) y la piel de la categoría que haya cambiado. Lo
   demás son los píxeles originales. La diferencia de píxeles sola no basta:
   el fondo inventado también es distinto del original.
3. **Sin cuenta, la cuota de ZeroGPU se agota en DOS pruebas al día** (medido:
   la tercera da «You have exceeded your ZeroGPU runs limit»). Con `HF_TOKEN`
   de una cuenta gratuita hay más. Los tests fuerzan `VTO_PROVIDER="none"`.
4. **`VTO_SPACE` es la dirección directa del Space, no su nombre.** Con el
   nombre, gradio_client pregunta a la API de huggingface.co, y en este equipo
   eso tardaba 168 s: huggingface.co anuncia IPv6, la red no lo encamina y
   Python espera a que caduque. El Space responde en 0,6 s. Por lo mismo, el
   analizador se carga primero de la caché local.
5. **Se encuadra a la persona antes de mandarla**: el modelo trabaja a 864 px
   de alto, y en una foto de cuerpo entero la prenda salía con un tercio de los
   píxeles. Desde el 10/11/2026 el encuadre depende de la prenda: para una
   «parte de arriba» va de la cabeza a medio muslo (`BAJO_LA_PRENDA`). Medido
   en las dos fotos de cuerpo entero: la persona pasa de 193 a 318 px de ancho
   en lo que ve el modelo, y de 220 a 338. Si la prenda llega al pie del
   cuadro se avisa de que se pruebe como «Vestido o mono». Solo arriba: no
   había ninguna prenda de abajo en el taller con la que medirlo.
6. **Licencias**: FASHN y onnxruntime son libres; los pesos del analizador
   derivan de SegFormer de NVIDIA, de uso NO comercial. Vale para un proyecto
   universitario, no para venderlo.
7. **FASHN va en el modo que NO borra la prenda vieja** (`segmentation_free=True`,
   el suyo por defecto) **y con 50 pasos**. Hasta el 10/11/2026 iba en el que
   borra, por una manga negra que quedó en un hombro el 28/09. Lo que no se
   había probado —las tres pruebas eran camisetas sobre camisetas— es una
   prenda MÁS GRANDE que la que se lleva puesta: borrando, el modelo la
   recorta al hueco de la vieja. Medido con un vestido largo de manga larga
   sobre camiseta y pantalón corto: borrando salió un minivestido y el
   estampado tapó el móvil que sujetaba; sin borrar llega a los tobillos y el
   móvil y las manos quedan como estaban. Y a 30 pasos ese mismo vestido, con
   la misma semilla, salió con dos agujeros en las rodillas; a 50, entero.
   `VTO_ERASE_FIRST=true` vuelve al modo de borrar: el modelo avisa de que sin
   borrar pueden quedar restos al pasar de larga a corta, y eso no se ha
   vuelto a medir.
8. **La piel NO entra en la zona por haber cambiado.** Así era, y el modelo
   (en modo borrar redibuja más) cortó el móvil del usuario, redibujó su mano
   y dejó un borrón beige: todo pasó al resultado. La piel que la prenda
   destapa o tapa ya entra por ser ropa en una de las dos imágenes; la que es
   piel en las dos se queda con sus píxeles.
9. **La prenda vieja que el analizador no ve**: el pliegue de la manga bajo el
   codo salió como «fondo». Se añade lo etiquetado como fondo que tiene el
   color de la prenda de al lado y está pegado a ella (medido: cubre el 94%
   del pliegue). Solo fondo: dejándola crecer sobre los brazos, se llevaba el
   antebrazo tatuado de otra foto.
10. **Los 502 de la pasarela de Hugging Face se reintentan; la generación,
    nunca.** Al usuario le falló dos veces seguidas: al conectar, y al
    DESCARGAR el resultado cuando el modelo ya lo había generado y cobrado de
    la cuota. Conexión y descarga (que hace `fashn._descargar`, no el cliente
    de Gradio, para poder repetirla) se reintentan tres veces; repetir la
    generación a ciegas podría gastar la cuota dos veces.
11. **Cada prueba lleva su semilla: `42 + id`.** Con una fija, repetir daba la
    MISMA imagen —el modelo se inventó un cordón y un collar sobre la camiseta
    roja, y repetir los devolvía idénticos—. El botón «Otra variante» vuelve a
    lanzar la misma combinación con otra semilla. Se descartó contar los
    intentos previos: el usuario borra pruebas, y la cuenta volvía atrás.
    Y se descartó detectar lo inventado por color PÍXEL A PÍXEL dentro de la
    prenda: daba falsos positivos en el canto de la zona y se dejaba el
    collar, que tiene tono de piel. Lo del punto 14 es otra cosa —manchas
    enteras contra la paleta de la prenda—, y el collar sigue sin detectarse.
12. **El fondo no se toma NUNCA del modelo.** El «fantasma» claro junto al
    hombro y el ribete claro de la prenda eran NUESTROS, no del modelo: donde
    la prenda vieja era más ancha que la nueva, y en el margen del canto, se
    copiaba el fondo que el modelo regenera, que no es el de la foto (cambió
    una línea de árboles por un horizonte claro). Ahí va ahora el fondo de la
    FOTO, continuado desde los píxeles de al lado (relleno de Telea).
    Promediarlo dejaba una mancha pálida sobre un fondo en franjas; y hay que
    alejarse del canto de la prenda vieja (`SOMBRA_DE_LA_PRENDA_VIEJA`), o su
    sombra tiñe el relleno de gris.
13. **«Fondo» es lo de FUERA de la silueta, no lo que el analizador llama
    fondo.** No tiene etiqueta para lo que la persona sostiene: el móvil sale
    como fondo, y en la primera prueba del vestido de noche el relleno
    arrastró su dorado y el negro de su cámara hasta los hombros. Y parte del
    abdomen que deja al aire una chaqueta corta también salió como fondo. Se
    tapan los huecos de la figura (`_solida`) y se exige el color del fondo
    de alrededor (4–15 de mediana el hueco de verdad, 73 la piel) y más
    parecido a él que a la piel de al lado.
14. **La ropa que el modelo se inventa se delata por el color.** Con una
    camiseta roja y la semilla 66 pintó debajo unas mangas largas verdes —en
    sus dos modos y con 30 y 50 pasos—; con la 70, no. Es azar de la semilla:
    para eso está «Otra variante». Distancia a la paleta de la prenda en Lab:
    18 de percentil 99 en las prendas bien puestas, 40–65 en lo inventado
    (`LEJOS_DE_LA_PRENDA = 30`). Donde tapaba piel vuelve la foto, y se
    avisa. Si «inventado» es más de media prenda no se quita nada: es la
    prenda entera con otra luz.
15. **Cada prueba guarda lo que devolvió el modelo, sin componer**
    (`raw_output_key`, `raw_box`, `model_params`), y `scripts/recomponer.py`
    rehace la composición sin gastar cuota. Sin eso, todo lo de arriba hubo
    que medirlo con un arnés aparte, pagando una prueba por cada idea.
16. **La «falta de nitidez» no era un defecto, y medirla lo demostró.** El
    diagnóstico vio 1,55 de laplaciano en la prenda frente a 4,29 en el resto
    y lo llamó «pegada». Las fotos de prueba no tienen grano que igualar
    (0,25 sobre 255), y con una prenda estampada la zona generada da MÁS
    detalle que el resto (17,7 frente a 4,3): la camiseta era lisa, nada más.
    No se añadió ni grano ni enfoque.
17. **El modelo dibuja a la persona más delgada, y la ropa se comía el brazo.**
    Medido el 12/11/2026 con un hombre musculoso y una camiseta de manga corta
    (prueba 30): el antebrazo que pinta el modelo tiene el borde de fuera en
    su sitio pero es mucho más fino, y el hueco de dentro lo ocupa la
    camiseta, que entraba encima del brazo real por «ser ropa». Ahora, en los
    tramos del brazo que la imagen generada deja al aire, el brazo de la foto
    se queda entero (`_brazos_al_aire`). Tres cosas que costaron: el eje se le
    busca al brazo GENERADO (largo y fino), no al de la foto, cuyo trozo
    visible puede ser corto y sin dirección; el corte sigue el dobladillo que
    dibujó el modelo, que es la parte del extremo que da a ropa y no a fondo;
    y sin dobladillo reconocible se corta donde acaba la piel generada —nunca
    «todo lo de más allá», que con una chaqueta de manga larga devolvía el
    brazo entero y borraba la manga—. Se descartó, midiéndolo, deformar la
    imagen del modelo hasta su silueta: el contorno exterior casi no se mueve
    (0,6 px). Lo que NO se arregla: la caída holgada de la prenda sobre el
    pecho, que es dibujo del modelo.
18. **Este modelo no reproduce un vestido de noche, y no es cuestión de
    parámetros.** El vestido del boceto (hombros caídos con drapeado, sirena,
    sobrefalda con cola) sale siempre como un palabra de honor en línea A a
    media pierna. Medido con la misma foto y semilla en cuatro
    configuraciones: `flat-lay`, tipo de foto `model`, guía 2,5 (deja además
    restos de la camiseta vieja) y la prenda estirada ×1,3 a lo alto. Y se
    descartó colocar la imagen de la prenda encima con su forma exacta: se ve
    pegada y tapa los muebles, porque una imagen plana no sabe qué hay
    delante. De paso salió por qué «tal cual» no puede ser: el vestido del
    boceto tiene proporciones de figurín —de la cintura al bajo hay 7,9 veces
    el ancho de la cintura; en una persona, unas 3,7—. El camino que queda es
    medir otro modelo (`ModeloDePrueba` ya lo permite), no ajustar este.

---

## El motor textil — lo que hay que saber antes de tocarlo

`backend/app/textil/`. Es donde está la matemática y donde se han cometido y
corregido los errores más caros.

| Archivo | Qué hace |
|---|---|
| `segmentar.py` | Qué píxeles son prenda. Se calcula UNA vez al subir y se guarda. |
| `retexturizar.py` | El motor determinista. Un solo camino: la fotografía de la prenda. |
| `boceto_ia.py` | De un boceto a la fotografía de la prenda. La IA, una vez. |
| `veta.py` | Por dónde corre el hilo en cada pieza: la raya sigue la manga. |
| `bloqueo.py` | Lo que hace fiable a la IA: solo aporta textura donde coincide. |
| `digitalizar.py` | De la foto de un rollo a un mosaico limpio: lisos, rayas, estampados. |
| `tela_propia.py` | La tela del usuario: una foto de móvil → mosaico, con avisos sobre la foto y la junta medida. Sin IA. |
| `tejido_ia.py` | Mosaicos sintetizados con IA y el cierre de juntas. |
| `filtros.py` | Desenfoque, reescalado, filtro guiado; todo en coma flotante. |
| `provider.py` | El contrato y el selector. |
| `openai_provider.py` | El acabado generativo de una prueba, tras el bloqueo. Ya sin botón en la interfaz. |

### La idea, en una frase

Una fotografía ya contiene lo difícil: dónde hay un pliegue, dónde da la luz.
Esa información depende de la **forma**, no del color, así que se separa
dividiendo el brillo de cada píxel entre el brillo típico de la prenda — y lo
que queda se traslada a la tela nueva.

### Cosas que costaron encontrarse

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
5. *(Camino RETIRADO el 2026-10-01: `vestir_boceto` ya no existe; la tela ya no
   se pinta sobre el dibujo. Se deja porque explica por qué.)*
   **Un boceto SÍ tiene luz, y darlo por supuesto costó el motor entero.**
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
7. **El fondo no es un color: es una superficie.** El recorte de una foto de
   camiseta incluía un manchón que después salía estampado de tela. Parecía la
   sombra proyectada y no lo era: medido, ese manchón tiene brillo **235 y el
   fondo 223** — es MÁS CLARO. Era el degradado del ciclorama.

   Un solo color de las esquinas no puede representar un fondo con degradado, y
   el umbral no estaba mal ajustado: **el modelo de fondo estaba mal
   planteado**. Ahora se ajusta una superficie cuadrática por canal al marco de
   la imagen, de forma robusta. Medido: la cobertura de la camiseta pasa de
   0,613 a 0,520 y la del boceto no se mueve.

   Se descartó frenar el relleno con la fuerza del borde —dejarlo pasar por
   cualquier sitio liso—: arreglaba la camiseta y **se comía un tercio del
   vestido**, porque el interior de un dibujo a lápiz también es liso. Entre el
   valor que funciona y el que destruye había un factor dos.
8. **El muestreo del mosaico era por vecino más próximo**, y el desplazamiento
   del pliegue se truncaba a entero. La tela no se curvaba: se escalonaba. Ahora
   es bilineal, con el módulo sobre los ÍNDICES para que la interpolación cruce
   la costura del mosaico sin partirse.
9. **La máscara de OpenAI va al revés que la nuestra.** Ahí lo TRANSPARENTE es
   lo que se edita. Mandarla sin invertir da una imagen plausible y equivocada.
10. **El halo de las fotos tenía tres causas, y el filtro guiado no era la
    cura.** Fondo que entraba como prenda (lo quita GrabCut, con la prenda
    SEGURA exigiendo además color distinto del fondo), el fondo mezclado del
    canto disparando la razón de luz (el sombreado se calcula ahora solo con
    prenda pura), y el borde de una máscara hecha a 512 px. Para eso último se
    confió primero en el filtro guiado y una prueba lo desmintió: con 6 px de
    error dejaba el borde a −5. Conserva la media donde la foto es lisa, y la
    franja sobrante ES fondo liso. El borde lo decide ahora el color local de
    prenda y fondo en una franja dudosa; el filtro guiado solo suaviza el canto.
11. **Las prendas oscuras no tienen poco contraste: tienen demasiado.** Medido
    en logaritmo: cazadora de cuero 0,92, camiseta negra 0,82, jersey 0,49,
    camiseta blanca 0,13. Se normalizan los pliegues hacia el rango de las de
    tono medio, se quita la textura del material viejo umbralizando por su
    propio nivel, y se limitan los brillos según la tela nueva.
12. **El doblado del estampado se mide en la PRENDA, no en el mosaico.** En
    fracciones del mosaico, un floral grande se ondulaba ±63 px.
13. **La veta se deduce del GROSOR, no de la dirección del borde.** El tensor de
    estructura daba «mangas» junto a cualquier borde recto. Una manga es una
    pieza estrecha (grosor local), alargada (≥2,5) y en diagonal (10–60°).
14. **En un boceto, la barrera es la línea de lápiz.** La sombra alrededor del
    figurín entraba como prenda; subir el umbral de color se colaba por los
    tramos débiles del contorno. El relleno puede comerse la franja exterior
    (14 px) sin cruzar trazos. Y la figura se detecta con CROMA absoluto: la
    saturación relativa se dispara en el grafito oscuro y agujereaba el vestido.
15. **Cerrar la junta de un mosaico periódico: desplazar un múltiplo del
    período y cortar por el camino de mínimo error.** Fundir a media anchura
    dejó fantasmales los vichy; fundir con rampa, hojas dobles en las palmeras.
    **Y el corte entra y sale por la misma columna** (12/11/2026): al cerrar el
    segundo eje, un corte que entraba por un sitio y salía por otro reabría la
    junta del primero. Con un estampado de motivos sueltos daba junta 7,4 y los
    motivos partidos; no se había visto porque las telas del catálogo no tienen
    motivos sueltos sobre un fondo liso.
16. **El cierre morfológico sella también el hueco entre el brazo y el cuerpo.**
    No sabe de colores: en el vestido negro del usuario la tela rellenaba ese
    hueco de axila a mano. Lo añadido por el cierre se devuelve al fondo si es
    claramente fondo Y mucho más parecido al fondo que a la prenda de al lado.
    La distancia al fondo sola no separaba el hueco (0,4 del umbral) de los
    túneles de la camiseta blanca (0,7), que sí hay que sellar.
17. **Nada que se amplíe desde 320 px puede ir por vecino más próximo**, tampoco
    las etiquetas de los paneles de la veta: salían costuras en escalera de 5 px
    y un serrucho de raya vertical por el filo de la manga. Pertenencia en coma
    flotante, suavizada, ampliada bilineal, y cada píxel a la pieza que gane.
18. **Una prenda blanca sobre fondo claro salía con un ribete blanco** al
    vestirla de un color oscuro. Dos causas. El borde se decidía por color
    donde prenda y fondo miden lo mismo (217 contra 217 en el canto de la
    camiseta blanca), y se llenaba de medias transparencias por DENTRO: ahí
    manda ya el recorte a 512 px (`SEPARACION_MINIMA`, medida: la camiseta da
    0,088 de mediana, el jersey gris —la siguiente— empieza en 0,26). Y el
    canto se mezclaba con la foto, que en esos píxeles aún tiene la prenda
    vieja: se mezcla con el FONDO de al lado. En un boceto no se aplica lo
    primero: el trazo, más oscuro que papel y vestido, sí lo encuentra el color.
19. **La tela del usuario (`tela_propia.py`) no tiene a nadie que elija el
    recorte**, como sí lo hubo con las fotos de la tienda: se toma el 80%
    central. La nitidez se mide con la medida de Crete et al. (2007), que
    compara la imagen consigo misma desenfocada y no depende de cuánto dibujo
    tenga la tela; la dirección sin cambios (a lo largo de una raya) no cuenta,
    o una raya perfecta sale «desenfocada». En una lisa no se mide: de ella
    solo se toma el color. Umbrales medidos en la tabla del módulo.
    `medir_junta` da 2,0 en un liso o una raya perfectos (la trama de tafetán
    va en contrafase con su período): el tope es 3,0, el mismo de las pruebas.

### Los parámetros están medidos, no elegidos a ojo

`DOBLADO_DEL_ESTAMPADO = 0.03`. Estuvo en 0,10 y **hubo que recalibrarlo al
pasar a mosaicos fotográficos**: el parámetro no cambió, cambió la frecuencia de
la textura sobre la que actúa. Con un cuadro nítido, 0,10 lo derrite en cintas y
el denim sale en vetas verticales. Medido de nuevo sobre vichy fotográfico: 0,05
todavía ondula, 0,03 sigue la curva del hombro conservando el cuadro, 0,015 no
se nota, y 0 deja una rejilla recta sobre una manga curva.

`RADIO_CIERRE = 5`: con 3 queda una ranura abierta en la camiseta blanca, y con
7 las perneras del vaquero siguen separadas. Si cambias uno, mídelo igual.

---

## La IA: dónde está y por qué está AHÍ y no en otro sitio

### Resumen, porque es lo primero que se pregunta

La IA está en tres sitios. Solo en el primero inventa, y ahí se le pide:

1. **Los materiales**: sintetiza el mosaico fotográfico de cada tela y
   reconstruye los estampados de los que la foto solo enseña una franja. Una
   vez por tela; lo usan todas las pruebas.
0. **La prenda de un boceto**: convierte el dibujo en la fotografía de la
   prenda. Una vez por boceto; el usuario la ve junto a su dibujo. Es lo único
   que la interfaz ofrece hoy con IA. Ver «Los bocetos».
2. **El acabado de una prueba** (opción «IA generativa»): detrás del BLOQUEO
   ESTRUCTURAL (`bloqueo.py`). Forma, estructura y color salen del render
   exacto; de la IA solo la textura fina donde coincide, y un tono monótono.
   Si coincide en menos de un 15% de la prenda —es otra prenda— se descarta
   entera. Medido: las cuatro salidas antiguas que eran otra prenda quedan
   descartadas al 100%; la prueba real sobre la camiseta, en la que el modelo
   devolvió la ESPALDA, sale como el frente con su etiqueta.
3. No en la geometría de una FOTOGRAFÍA. Nunca.

El acabado (2) sigue en el backend —`method: "ai"`— pero la pantalla de
pruebas ya no lo ofrece: el usuario pidió que la IA generativa se use solo
para los bocetos.

**`AI_PROVIDER=openai`.** El valor por defecto del repositorio es `none`, porque
que clonarlo empiece a gastar dinero de alguien sería una trampa. Un valor
desconocido **hace fallar el procesado**, nunca cae al motor local en silencio.

### La causa raíz, y está en la documentación de OpenAI

> *«masking with GPT Image is entirely prompt-based»* — y el modelo *«may not
> follow mask shapes with complete precision»*.

**La máscara es una sugerencia, no una restricción.** No existe parámetro de
intensidad, ni de ruido, ni condicionamiento estructural: nada equivalente a un
ControlNet o a un `strength`. `images.edit` **regenera la imagen entera**, no
parchea la zona marcada.

Con eso sobre la mesa, pedirle a `images.edit` que conserve la geometría de una
prenda no es un problema de prompt: es pedir una garantía que la API no ofrece.
Se midió seis veces y la sexta con TODO bien puesto —modelo de precisión,
fidelidad alta de verdad, máscara binaria, tamaño nativo, calidad alta, la tela
como segunda imagen y partiendo del retexturizado correcto—: devolvió una seda
espléndida sobre un vestido que no era el del boceto.

### Por eso la IA no está en el camino de la geometría

```
ficha de la tela + mosaico procedural
    --[IA, UNA VEZ POR TELA]--> mosaico fotográfico, guardado en el catálogo
prenda + máscara + mosaico
    --[determinista, SIEMPRE]--> resultado con la geometría exacta
```

La geometría —silueta, pliegues, costuras, la persona— sale del retexturizado,
que es una multiplicación por píxel y **por construcción no puede mover nada**.
Lo que a ese camino le faltaba no era geometría: era que el mosaico pareciera
tela de verdad. Y eso sí lo hace de maravilla un modelo generativo, porque en un
trozo de tela plano no hay diseño que respetar.

`app/textil/tejido_ia.py` y `scripts/telas_fotograficas.py`. Se paga una vez por
tela y para siempre, en vez de una vez por comparación: doce telas son doce
llamadas. Y se conserva lo que hace útil comparar, que entre dos pruebas lo
único que cambie sea la tela.

**El mosaico se cierra después, y se mide.** Un modelo no devuelve bordes que
encajen, y pedírselo por escrito no funciona; se funde consigo mismo desplazado
media anchura (`hacer_repetible`) y se comprueba con `medir_junta`, que da ~1
cuando no hay junta. Medido: tafetán 1,03, denim 0,76, vichy 1,30.

### Los cinco defectos de implementación que había además

Ninguno era el prompt.

| # | Qué pasaba | Arreglo |
|---|---|---|
| 1 | **El modelo era `gpt-image-1-mini`**, el más débil de los ocho que acepta `images.edit`, y **el único que rechaza `input_fidelity`**. Como ese 400 se reintenta sin el parámetro, TODAS las llamadas salían con la fidelidad desactivada sin que se notara. | `gpt-image-2.5-sunburst`, que es el de precisión de edición. |
| 2 | **La tela nunca se le enseñaba**: viajaba como texto. Imaginarse el material y imaginarse la prenda son, para un modelo generativo, el mismo acto. | Va como segunda imagen; la API admite 16 y aplica la máscara sobre la primera. |
| 3 | **La máscara iba difuminada** (13–25 px de pluma, un 3% de los píxeles) a una API que solo define alfa = 0. Lo indefinido pasaba justo en el contorno. | Binaria para la API; la pluma se queda para nuestra composición. |
| 4 | **Se forzaba a 1024x1536 y se devolvía al tamaño original**: dos remuestreos de la geometría para nada. | Tamaño nativo múltiplo de 16, con reintento a los tres fijos para los modelos que no lo admiten (se descubrió con un 400: la capacidad es POR MODELO, no de la API). |
| 5 | **`quality` sin poner**, o sea `auto`, justo cuando lo que se mira es el detalle fino. | `high`. |

### Control de gasto, en tres sitios

1. El límite mensual del panel de OpenAI. Lo puso el usuario.
2. `AI_TRIALS_PER_USER_PER_DAY` (20), ventana móvil de 24 h. Suma las prendas
   generadas de bocetos y las pruebas con IA.
3. **Las pruebas automatizadas no pueden gastar nunca.** `conftest.py` tiene un
   fixture `autouse` que fuerza `AI_PROVIDER="none"`. Sin él, la suite entera
   —71 tests, decenas de veces al día— generaría imágenes facturadas.

**Sin reintentos automáticos**, con DOS excepciones y las dos gratis: un 400 por
`input_fidelity` y un 400 por `size` se rechazan ANTES de generar imagen. Una
tabla de qué modelo admite qué caducaría con el siguiente modelo.

---

## Reparto de acceso

Públicos: `/api/health`, el catálogo de telas en lectura, `POST /api/users` y
`POST /api/auth/login`. Todo lo demás —prendas, telas propias, pruebas, fotos
de persona y pruebas sobre ellas— exige `Authorization: Bearer <token>`.

El catálogo (`/api/fabrics`) busca SOLO telas con `owner_id` vacío, y las telas
propias (`/api/my-fabrics`) SOLO las del usuario del token: una tela de un
taller no aparece ni se toca por el camino del otro. Al probar, la tela tiene
que ser del catálogo o del usuario (`FabricRepository.get_visible`).

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
