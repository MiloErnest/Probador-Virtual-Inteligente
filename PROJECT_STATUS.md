# Estado del proyecto

> Documento vivo. Se actualiza al cerrar cada etapa.

**Etapa actual:** prueba virtual de telas, y el probador sobre la foto de una persona.
**Última actualización:** 2026-09-27

---

## Qué pasó el 2026-09-27 (segunda parte)

El usuario pidió un ejecutable para arrancarlo todo, y saber si las prendas
funcionan bien.

- **`Iniciar Probador.exe`** (`lanzador/`): arranca backend y frontend sin
  ventanas, espera a que respondan, abre el navegador y los apaga al cerrarse.
  Verificado las dos salidas: pulsando Enter, y matando el proceso de golpe
  (como cerrar con la X) — los puertos 8000 y 5173 quedan libres y no queda
  ningún node.exe. Compilado con el csc de .NET Framework 4, sin instalar nada.
- **Banco de 8 prendas × 3 telas repasado a mano.** Encontró un defecto que
  venía de antes: la camiseta blanca vestida de terracota salía con un ribete
  blanco deshilachado. Arreglado (CLAUDE.md, lección 18), con dos pruebas que
  fallan con el código anterior. Solo cambian el canto de la camiseta blanca
  y un trozo de fondo entre el puño y el cuerpo del jersey gris; el boceto y
  las demás prendas no se mueven ni un píxel.
- **El probador por la API**: la cuota gratuita seguía agotada (se renueva a
  las 24 h del primer uso). La #42 sigue abierta.
- **Las fichas del catálogo de las telas reales** llevaban debajo una tira de
  la foto de la estantería, ampliada: al usuario le pareció, con razón, un
  recorte mal hecho. Ahora la foto de ficha es solo la tela digitalizada
  (`_ficha` en `scripts/seed_telas_reales.py`), también en el floral, que
  enseñaba la foto con sus arrugas. Recargadas las 14 con el script, gratis.
- **Acceso directo «Probador Virtual» en el escritorio** del usuario, al
  lanzador. Es local: no está en el repositorio.

## Qué pasó el 2026-09-27

El usuario pidió revisar el proyecto entero y dejarlo funcionando, y redefinió
el probador: **no una cámara en vivo, sino un probador por imágenes**. Sube una
foto suya, elige una prenda de su taller —la que ya editó con una tela, tal
cual, sin volver a generarla— y ve cómo le queda, en cualquier postura,
conservando a la persona y sin que la IA rediseñe la prenda. Y que no fuera un
flujo aparte que duplicara el taller. Antes había dicho que no quiere seguir
pagando APIs.

### Lo que se construyó

| Pieza | Qué es |
|---|---|
| `app/probador/` | Encuadrar a la persona, vestirla con FASHN VTON 1.5 (Space gratuito de Hugging Face) y conservarla. |
| Conservación | Un analizador de personas en CPU dice qué es cada píxel; del modelo solo entra la ropa de la categoría y la piel que cambie. |
| `person_photos`, `try_ons` | Migración `32d71eca2214`. La prenda sale de una prueba de tela o de una prenda subida. |
| `/probador` | Tu foto, la prenda (con tela o tal cual, o subir una nueva con el alta del taller), la categoría, y el resultado junto al original y a la prenda enviada. |
| Enlaces | «Probármela» en cada prueba de tela y en cada prenda del taller. |
| Retirado | La cámara, su catálogo `garments`, `scripts/seed.py` y MediaPipe (el modelo de 5,6 MB salió del repositorio). |

### Lo que se midió con el modelo real

Dos pruebas reales antes de que se agotara la cuota: una persona sentada con la
camiseta de rayas azul rey del usuario, y otra frente a un espejo con la de
palmeras. Las dos veces la prenda salió con su dibujo y su color, siguiendo la
postura, en ~28 s. **Y las dos veces el modelo cambió cosas fuera de la
prenda** (6% y 2% de la foto): una ventana, un cuadro de la pared, un
cinturón. La conservación los devuelve a la foto original; verificado sobre
esas dos salidas.

### La revisión encontró, y se arregló

- **El hueco entre el brazo y el cuerpo se pintaba de tela** (el vestido negro
  del usuario): lo sellaba el cierre morfológico. Ver CLAUDE.md, lección 16.
- **Costuras en escalera y serrucho en el filo de las mangas** de las rayas:
  paneles de la veta ampliados por vecino más próximo. Lección 17.
- **Borrar una prenda dejaba huérfanas las imágenes de sus pruebas.**
- **Textos que no eran verdad**: la cuenta «no guarda ni una foto» (guarda
  prendas y pruebas), «tu cámara no sale de tu equipo», «un boceto necesita
  IA», el `.env.example` recomendando `gpt-image-1-mini`, y un README que
  documentaba endpoints `/api/try-on-sessions` que ya no existían.
- **El probador tardaba 175 s en fallar**: preguntar a huggingface.co desde
  Python tarda 168 s en esta red (IPv6 anunciado y no encaminado). Con la
  dirección directa del Space, 6 s.

## Qué pasó el 2026-09-26

El usuario pidió cuatro cosas: dar de alta las telas reales de la tienda a
partir de tres fotos; arreglar las telas que se veían mal; que el retexturizado
funcionara con cualquier prenda y no solo con algunas; y que la IA funcionara
«al 100%, sin devolver otra prenda». Y pidió investigar cómo lo resuelven los
probadores que funcionan.

### Lo que dice la investigación, y lo que decide

Ningún sistema que funcione conserva la geometría con un prompt. Los
configuradores de tela del comercio electrónico (Style3D, Imagine.io, NunoX) y
la investigación sobre retexturizado de prendas (Pattern Guided UV Recovery,
arXiv 2407.10137) NO generan la prenda: extraen máscara, sombreado y relieve, y
componen la tela de forma determinista. Los generativos que sí conservan la
forma (ZeST, IDM-VTON, CatVTON) usan condicionamiento estructural duro —
profundidad por ControlNet, codificadores de prenda— que la API de OpenAI no
ofrece. De ahí la arquitectura de esta etapa.

### Lo que se hizo

| Pieza | Qué es |
|---|---|
| Catálogo reparado | 11 telas con la foto borrada por un fallo del script de mosaicos (foto y mosaico eran el mismo archivo). Vichy fantasmales rehechos: el cierre de junta ahora mide el período y corta por el camino de mínimo error. |
| 14 telas reales | `app/textil/digitalizar.py` + `scripts/seed_telas_reales.py`: 5 rayas, 6 lisos, el floral y 2 estampados reconstruidos por IA, desde las fotos de la tienda (`scripts/muestras/`). |
| Recorte robusto | GrabCut para fotos; borde decidido con el color local; barrera de lápiz en bocetos; figura por croma. |
| Sombreado robusto | Solo con prenda pura, pliegues normalizados, textura del material viejo quitada, brillos según la tela nueva. |
| Veta | `app/textil/veta.py`: la raya corre a lo largo de las mangas. |
| Bloqueo estructural | `app/textil/bloqueo.py`: la IA ya no puede devolver otra prenda. |

Todo medido en un banco de 8 prendas × 3 telas: las tres subidas del usuario y
cinco fotos reales (camisa, camiseta blanca, cazadora de cuero, vaquero, jersey).

## Qué pasó el 2026-09-18

El usuario aportó el **Product Vision Board** del proyecto, y el producto que
describe no es el que había: no es un probador de ropa para quien se la pone,
es una **herramienta de venta para tiendas de telas**, cuyos usuarios son
diseñadores, modistas y talleres que tienen que **elegir tela para una prenda**.

Eso invierte el modelo. El catálogo pasa a ser de **telas**; las prendas las
sube el usuario. El probador con cámara se conserva como funcionalidad
adicional, pero no es el producto.

### Lo que se construyó

| Pieza | Qué es |
|---|---|
| `fabrics` | Catálogo de la tienda: referencia, composición, gramaje, ancho de rollo, precio/m, color, dibujo, mosaico. |
| `garment_uploads` | La prenda o boceto del usuario, con su recorte ya calculado y guardado. |
| `fabric_trials` | Una prueba: prenda × tela → imagen. Guarda motor, duración y tokens. |
| `app/textil/` | El motor: recorte, retexturizado de foto, retexturizado de boceto, y proveedor generativo. |
| 4 pantallas nuevas | Portada, catálogo de telas, taller, y comparación. |

Migración `84f6b95eefae`. **No toca nada de lo que ya había**: `garments` sigue
siendo el catálogo del probador con cámara.

---

## Lo que funciona

### El motor de telas

- [x] **Recorte automático** al subir, por relleno desde los bordes con umbral
      adaptativo, cierre morfológico y tapado de cavidades. ~200 ms.
      Funciona igual con una foto que con un boceto.
- [x] **Retexturizado de fotografía**: separa la luz del color dividiendo por el
      brillo propio de la prenda, y multiplica la tela nueva por esa razón. En
      luz lineal. ~500 ms.
- [x] **El estampado se dobla con los pliegues**, desplazando las coordenadas de
      la textura según el gradiente del modelado.
- [x] **Se conservan costuras, botones y bolsillos**, devolviendo una fracción
      del detalle fino después de borrar la trama del tejido viejo.
- [x] **Retexturizado de boceto**: separa el dibujo en trazo y sombreado. El
      sombreado del lápiz pasa a ser la luz que multiplica la tela —los pliegues
      que se ven son los que dibujó el diseñador— y el trazo se conserva intacto
      por encima. ~500 ms. Si el dibujo no trae tono, cae al volumen inventado.
- [x] **La figura sale del recorte**: en un figurín, la cara, el pelo y los
      brazos ya no se pintan de tela.
- [x] **La IA sintetiza el MOSAICO de la tela**, no la prenda: una vez por tela,
      se guarda en el catálogo, y después lo usa el motor determinista. Es lo que
      permite tener material fotográfico Y geometría exacta a la vez.
- [x] **El mosaico generado se cierra para repetirse sin junta**, y se mide
      (tafetán 1,03, denim 0,76, vichy 1,30; 1 es perfecto).
- [x] **El fondo se modela como superficie**, no como un color: un ciclorama con
      degradado ya no entra en el recorte.
- [x] **Motor generativo de edición con OpenAI**, opt-in, con traducción de
      errores a mensajes accionables y registro de tokens. Conserva intacto todo
      lo que no es prenda; el interior lo reinterpreta y está medido seis veces.
- [x] **Aviso cuando el recorte sale dudoso**, antes de que el usuario gaste
      pruebas sobre una máscara rota.

### Backend

- [x] Catálogo de telas: listar con filtro por dibujo, ficha completa, alta,
      edición, foto de catálogo y mosaico por separado.
- [x] Prendas del usuario: subir, listar, ver, borrar. Todo filtrado por token.
- [x] Pruebas: crear (202 + sondeo), listar, filtrar por prenda, borrar.
- [x] Techo de gasto por usuario y ventana móvil de 24 h.
- [x] **96 pruebas automatizadas, en verde.** Y **no pueden gastar dinero ni
      cuota**: un fixture `autouse` fuerza `AI_PROVIDER="none"` y
      `VTO_PROVIDER="none"`.
- [x] Fotos de persona: subir (enderezada, a 2048 px y sin metadatos), listar,
      borrar con todas sus pruebas.
- [x] Pruebas sobre persona: crear (202 + sondeo), listar, borrar. La prenda
      sale de una prueba de tela terminada o de una prenda subida, y siempre
      del usuario del token.

### Frontend

- [x] Portada que cuenta el producto del Vision Board.
- [x] Catálogo de telas con ficha técnica completa y filtro por dibujo.
- [x] Taller: subir prenda o boceto, con la diferencia explicada.
- [x] Comparación lado a lado, con el original como referencia, y sondeo.
- [x] **Selector de motor en la pantalla de pruebas.** Hasta hoy la IA
      estaba integrada y era **inalcanzable desde la interfaz**: el cliente
      aceptaba `method` y la pantalla nunca lo mandaba. Al elegir IA sale
      antes lo que va a pasar y lo que cuesta.
- [x] **Probador por fotos** (`/probador`), verificado en el navegador hasta la
      llamada al modelo: sube, elige, lanza, sondea y enseña el error de cuota
      traducido. En móvil, sin desbordamiento lateral.
- [x] Build de producción verificado: 222 KB (sin MediaPipe).

---

## Verificación hecha el 2026-09-18

**Backend.** `pytest` → 71 en verde. `alembic upgrade head` aplicado sobre la
base real, `alembic check` limpio. 12 telas sembradas.

**Frontend.** `tsc --noEmit` limpio, `npm run build` correcto. La portada carga
y pinta las telas reales de la base.

**El motor, mirando los resultados.** 5 prendas × 5 telas. El recorte tarda
~200 ms y el retexturizado ~500 ms. Se corrigieron tres defectos encontrados
así: la camiseta blanca agujereada, el contorno dentado de la chaqueta de
cuero, y el estampado troceado en moaré.

**La API de OpenAI, con llamadas reales.** Es lo único que no se puede
verificar sin gastar. Tres llamadas, y las tres dijeron algo:

| # | Qué se probó | Resultado |
|---|---|---|
| 1 | `gpt-image-1-mini` + `input_fidelity=high` | 400: el mini **no admite** ese parámetro. Gratis: se rechaza antes de generar. |
| 2 | `gpt-image-1-mini` sin fidelidad | OK en 47 s, 7.880 tokens. **No conservó el diseño.** |
| 3 | `gpt-image-1` + `input_fidelity=high` | OK en 46 s, 12.935 tokens. **Tampoco.** |

El boceto de prueba tenía cartera de botones, cinco botones, bolsillo de pecho,
cuello camisero y costuras de manga. Las dos veces volvió convertido en una
túnica lisa de cuello barco.

**El camino determinista de boceto conserva todo**, en 320 ms y gratis.

### La cuarta llamada, ya con el selector puesto

Se lanzó por el HTTP real —token firmado, `POST /api/trials` con
`method: "ai"`, sondeo hasta `completed`— sobre el **boceto del propio
usuario**, un croquis de vestido de noche, con tafetán de seda burdeos:

| | Tiempo | Coste | Resultado |
|---|---|---|---|
| IA generativa | 32 s | 3.225 tokens | Vestido fotorrealista, **con otro diseño** |
| Retexturizado | 1,7 s | gratis | Silueta exacta, **pero pinta también a la modelo** |

Dos cosas que solo se ven con un dibujo real:

1. **El reintento de `input_fidelity` funciona.** Había una prueba fallida en la
   base, de código anterior al arreglo, con el 400 del mini. Con el código de
   ahora la misma petición sale adelante.
2. **La IA vuelve a cambiar el diseño, y esta vez es más engañoso**: el croquis
   es palabra de honor, sin mangas, con drapeado cruzado en el pecho; volvió con
   cuello redondo cerrado y manga larga. La imagen es preciosa, y por eso
   engaña: no se ve que está mal si no tienes el boceto al lado. La comparación
   lado a lado deja de ser un adorno.

---

## Errores conocidos y limitaciones

| # | Descripción | Impacto | Plan |
|---|---|---|---|
| 42 | **La generación con éxito por la aplicación entera no se ha podido ver todavía.** Las dos pruebas reales se hicieron con un script, y la conservación se verificó sobre sus salidas; por la API y la interfaz solo se llegó al error de cuota, porque sin cuenta son dos pruebas al día y se gastaron midiendo. | Alto | Con `HF_TOKEN` (cuenta gratuita) o al día siguiente: lanzar una prueba desde `/probador` y mirarla. |
| 43 | **Cuota gratuita pequeña**: ~2 pruebas al día sin cuenta. Con cuenta gratuita, más, pero sigue siendo una cuota diaria compartida por todos los usuarios de la instalación. | Medio | Suficiente para una demostración. Para un uso real, cuenta PRO de Hugging Face o un servidor con GPU propio. |
| 44 | **La prenda sale más blanda que el resto de la foto** en fotos grandes: el modelo trabaja a 864 px de alto y la foto se conserva a su resolución. El encuadre de la persona lo reduce, no lo elimina. | Medio | Es el límite del modelo. |
| 45 | **El analizador de personas es de uso no comercial** (pesos derivados de SegFormer de NVIDIA). | Bajo | Vale para el proyecto universitario. Para venderlo, otro analizador. |
| 46 | **La foto sale del servidor** hacia un Space público de Hugging Face. Se avisa en pantalla antes de subirla, y se guarda aquí sin metadatos. | Medio | Asumido y dicho. La alternativa es alojar el modelo. |
| 47 | **Las pruebas de tela antiguas siguen con los defectos de su momento** (el vestido negro con los bloques junto al torso). Se decidió no reescribir el historial. Como el probador usa la imagen guardada, una prueba vieja lleva sus defectos a la persona. | Bajo | Repetir la prueba de tela: sale ya con el motor corregido. |
| 39 | **El aporte visible de la IA al render es pequeño.** Con el bloqueo, la prenda está garantizada, pero de la IA solo entra la textura fina donde coincide. En la prueba real sobre la camiseta coincidió en un 17% — y el modelo había vuelto a devolver la ESPALDA de la camiseta. | Medio | Es el límite de la API: sin condicionamiento estructural no hay más que tomar sin arriesgar la prenda. Un proveedor con ControlNet de profundidad (ver «Próximos pasos») lo cambiaría. |
| 40 | **Una prueba con IA sobre una foto grande tarda más de un minuto** (71 s en 2048 px). El render determinista ya se optimizó: de 13,5 s a 3,3 s en 3 MP, con el mismo resultado (diferencia máxima de 4 niveles sobre 255). | Bajo | El corte del sondeo se subió a 150 s. Casi todo el minuto es la llamada al modelo. |
| 41 | **Los mosaicos IA de las telas de demostración viejas exageran la trama** (la franela sale como cestería). | Bajo | Son telas de demostración; las reales de la tienda salen de sus fotos. Rehacer con una instrucción por tipo de tela, o retirarlas. |
| 37 | ~~**Los mosaicos fotográficos solo están hechos para 3 de las 12 telas**~~ **RESUELTO**: el usuario los generó todos. Y el script tenía un fallo grave, ya corregido: borraba la foto de catálogo. Texto original: (tafetán, denim y vichy). Las otras nueve siguen siendo procedurales. | Medio | `python -m scripts.telas_fotograficas --aplicar`. Son 9 llamadas, ~27.000 tokens, una sola vez. |
| 38 | **La síntesis del mosaico no siempre acierta el ligamento.** El tafetán volvió con una trama más gruesa de lo que es una seda de 90 g. | Medio | La ficha ya le da gramaje y ligamento; falta iterar el texto de `_instruccion` y medir. O fotografiar el rollo real, que sigue siendo mejor. |
| 35 | ~~**La sombra proyectada de una prenda entra en el recorte y se pinta.**~~ **RESUELTO, y no era una sombra.** Medido, el manchón tiene brillo 235 y el fondo 223: es MÁS claro. Era el degradado del ciclorama, no una sombra. | — | El fondo se modela con una superficie cuadrática ajustada al marco, de forma robusta, en vez de con un color de las esquinas. Cobertura de la camiseta 0,613 → 0,520; el boceto no se mueve. |
| 36 | **En el croquis, la tela invade el escote y los hombros desnudos.** Sigue abierto. La exclusión de figura acierta con el pelo, la cara y los brazos, pero el pecho descubierto queda dentro del recorte. | Medio | Se probó detectar la piel pálida por TONO (10–45°, saturación 0,06 frente a 0,023 del corpiño): agujereaba la falda, cuyo sombreado tiene zonas cálidas. Exigir que estuviera unida a la figura tampoco: el brazo baja pegado al vestido. Hace falta un modelo aprendido de análisis de personas, o que el usuario retoque la máscara. |
| 30 | **El camino generativo no conserva el diseño** — pero su SALIDA ya sí, por el bloqueo estructural. Medido **siete** veces, la última devolvió la espalda de la camiseta: los dos modelos, con `input_fidelity=high`, una camisa y un vestido, y las dos últimas **partiendo del retexturizado ya correcto y pidiendo solo pulir**. Rediseña igual. Es una limitación del modelo, no de la integración. | Alto | Por eso la IA es opt-in y el camino por defecto es determinista. La interfaz lo advierte. Si aparece un modelo que sí lo conserve, es cambiar `OPENAI_IMAGE_MODEL`. |
| 34 | ~~**En un croquis de moda, el recorte pinta también a la modelo.**~~ **RESUELTO.** La máscara es «todo lo que no es fondo», y en un dibujo de figurín eso incluye la cara, el pelo y los brazos, que salen del color de la tela. Se vio con el boceto del usuario. | — | Se separa por saturación: el lápiz es acromático (0,02) y la figura no (0,10+). Con salvaguarda: si lo detectado pasa del 30% del recorte es una prenda de color, no una persona, y no se quita nada. Medido: el croquis pierde un 4,3%; la fotografía de camiseta, 0,0%. |
| 31 | **El retexturizado no cambia cómo CAE la tela.** Si la foto es de un vestido fluido, una lona rígida caerá como el vestido: los pliegues son los de la foto. | Medio | Es el límite de la técnica. Simular el tejido es otro problema y bastante mayor. Se dice en la portada. |
| 32 | **Los mosaicos del catálogo son generados, no fotografías de tela real.** Son creíbles y seamless por construcción, pero no son telas de verdad. | Medio | Para el producto real, la tienda aliada fotografía sus rollos y se recorta un cuadrado limpio. Sale mejor y es gratis. |
| 33 | **El volumen de un boceto es inventado.** Sale de la distancia al borde, no de información del dibujo. | Bajo | Es honesto y se avisa. No hay forma de deducir volumen de un dibujo de líneas. |
| 27 | **Una prenda casi del color del fondo no se puede recortar**, y no es cuestión de ajustar el umbral. Medido: fondo (217,218,212) contra tela en sombra (217,217,217). | Alto | Se detecta y se avisa. La solución es una fotografía sobre fondo que contraste. |
| 24 | ~~El probador con cámara no se ha probado con una persona real.~~ **RETIRADO**: la cámara se sustituyó por el probador por fotos. | — | — |
| 25 | ~~El probador con cámara no tiene oclusión.~~ **RETIRADO** con la cámara. En el probador por fotos, una mano delante de la prenda conserva sus píxeles originales. | — | — |
| 15 | **`BackgroundTasks` no sobrevive a un reinicio.** Si el proceso se para mientras una prueba está en `processing`, se queda ahí. Con el motor determinista son 500 ms de ventana; con el generativo, 45 s. | Medio | `status` está modelado, así que meter una cola no obliga a rehacer la tabla. |
| 4 | Los tests usan SQLite, no PostgreSQL. | Medio | Se activaron las claves ajenas (`PRAGMA foreign_keys=ON`); sin eso no se validaba ninguna restricción de integridad. |
| 5 | **El proyecto está dentro de OneDrive.** | Medio | Mover a `C:\dev\` o excluir `node_modules` y `.venv`. |
| 20 | **Las imágenes de Docker nunca se han construido.** | Medio | `docker compose --profile full up -d --build`. |
| 8 | Sin límite de peticiones. **Incluye el login.** | Medio | Antes de exponer la aplicación públicamente. |
| 10 | **El token se guarda en `localStorage`.** | Medio | Primer punto a revisar antes de un despliegue público. |
| 11 | **Cualquier usuario registrado puede dar de alta telas.** No existe la figura de administrador. | Bajo | Columna `is_admin` cuando haya un panel que la justifique. |
| 14 | **El registro no verifica que el buzón exista.** | Medio | Se resolverá con el acceso mediante Google. |

---

## Decisiones técnicas

### De esta etapa

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| **El camino por defecto es determinista, también para bocetos** | Mandar los bocetos a la IA | Se midió con llamadas reales: dos modelos, con y sin `input_fidelity=high`, y las tres veces el modelo devolvió una prenda distinta. Para un producto que promete «mira TU diseño con otra tela», eso es el resultado equivocado — y encima se cobraba por él. |
| **La IA se queda, pero como opción** | Quitarla | Sabe hacer algo que la otra vía no puede: convertir un dibujo de líneas en una imagen fotorrealista. Eso tiene valor real; lo que no tiene sentido es que sea el camino por defecto de un producto cuya promesa es la fidelidad al diseño. |
| **Retexturizado en vez de generación, para fotos** | Generar la imagen con IA | Tres razones, y la tercera es la que manda: es gratis, es cien veces más rápido, y es **determinista**. Comparar cuatro telas lado a lado solo significa algo si lo único que cambia entre las cuatro es la tela. Un modelo generativo redibuja el corte en cada llamada. |
| **Dividir el brillo entre el brillo propio de la prenda** | Multiplicar la tela por el brillo | Multiplicar mezcla forma y color: una prenda azul marino deja la tela nueva oscura, y una blanca la deja plana. Dividiendo, lo que queda es solo la forma. |
| **Multiplicar en luz lineal** | Multiplicar en sRGB | Los valores de un PNG llevan una curva encima; multiplicar sobre ellos no multiplica luz y las sombras salen más oscuras de lo que deberían. Cuesta dos funciones. |
| **Desenfoque y reescalado en coma flotante** | Usar los filtros de Pillow | Pillow trabaja en enteros de 0 a 255. Sobre una imagen no se nota; sobre un campo del que se calcula el gradiente, los escalones de 1/255 son casi toda la señal. Síntoma: el estampado troceado en moaré. **Se cometió dos veces**: la segunda al optimizar, cuantizando antes de ampliar. |
| **Derivar en pequeño y ampliar el gradiente** | Ampliar el campo y derivar | Un gradiente de un campo de frecuencia muy baja también es de frecuencia muy baja, así que ampliarlo no inventa nada. Derivar algo ya interpolado, sí. |
| **Limpiar el ruido en la DECISIÓN, no en el resultado** | Apertura morfológica sobre la máscara | La apertura arregló el contorno dentado de la chaqueta y **se comió el 7% de la camiseta blanca**: erosionar borra lo fino, y lo fino era prenda. Suavizando el mapa de distancias antes de umbralizar, los picos desaparecen y la cobertura no se mueve. |
| **Cierre morfológico + tapado de cavidades** | Solo cierre | El cierre sella la boca del túnel y deja la cavidad detrás, que sale como un agujero en mitad de la prenda. |
| **El recorte se calcula al subir y se guarda** | Calcularlo al probar | Se necesita idéntico para cada tela. Guardándolo, probar diez telas son diez multiplicaciones en vez de diez recortes. |
| **La escala del estampado se mide sobre la PRENDA** | Sobre la imagen | Con la imagen, la misma tela cambiaría de tamaño según el margen que tuviera la foto, y dos pruebas de la misma prenda dejarían de ser comparables. |
| **El mosaico se repite sin espejar** | Espejar para ocultar las uniones | Espejando, una raya se convierte en un galón en cada unión. En confección la dirección del hilo es un dato real. |
| **Dos imágenes por tela: foto y mosaico** | Una sola | La foto de catálogo lleva orillo y dobleces; repetirla sobre una camisa los mete cuarenta veces. |
| **`fabrics` aparte de `garments`** | Una tabla con un campo «tipo» | Son inventario de una tienda de telas y ropa para probarse delante del espejo. En una tabla, la mitad de las columnas estarían siempre vacías. |
| **El motor lanza su propio error** | Reutilizar `ValidationError` de servicios | Creaba un ciclo de importación que solo reventaba según el orden de carga. El ciclo era el síntoma; el problema es que una capa de abajo conocía la de arriba. |
| **Un fixture `autouse` que apaga la IA en los tests** | Confiar en no ejecutar esos tests | La suite lee el `.env` real. Con `AI_PROVIDER=openai` puesto —que es lo normal mientras se trabaja en esa parte— 71 tests × decenas de ejecuciones al día generarían imágenes facturadas. |
| **Claves ajenas activadas en SQLite** | Dejar el valor por defecto | SQLite las trae desactivadas, así que los tests no validaban ninguna restricción de integridad. Se descubrió porque borrar una prenda dejaba sus pruebas vivas solo en los tests. |
| **Un reintento, y solo uno** | Ninguno, o varios | Si la API rechaza `input_fidelity` con un 400, se reintenta sin él. Un 400 se rechaza antes de generar imagen, así que es gratis; y una lista de qué modelo admite qué caducaría con el siguiente modelo. |
| **`gpt-image-1-mini` por defecto** | El modelo completo | Cuesta un 64% menos en tokens (7.880 contra 12.935) y **no conserva mejor el diseño**. Pagar más por lo mismo no tiene defensa. |
| **202 al crear una prueba** | 200 síncrono | El motor determinista tarda medio segundo y el generativo cuarenta y cinco. Con dos contratos distintos, el frontend tendría que saber qué motor va a correr antes de pedirlo. |

### Anteriores, todavía vigentes

| Decisión | Motivo |
|---|---|
| Monolito modular por capas | Con un dominio poco conocido, los límites de servicio se pondrían mal. |
| SQLAlchemy síncrono | Consultas triviales; más simple de depurar y testear. |
| `create_all` fuera del arranque | Dos fuentes de verdad para el esquema divergen en silencio. |
| `PyJWT` sobre `python-jose` | Mantenimiento irregular e historial de CVEs. |
| HS256 fijado en código | Un algoritmo configurable se puede degradar a `none`. |
| 404 en recursos ajenos | Un 403 confirma que el recurso existe. |
| Token en `localStorage` | En memoria, cada recarga cierra la sesión. Riesgo asumido (#10). |
| `image_key` en BD, `image_url` en la API | Migrar a S3/R2 no obliga a reescribir filas. |
| Enums como `VARCHAR` sin CHECK | Añadir un valor a un ENUM nativo exige `ALTER TYPE`. |
| `bcrypt` directo | passlib 1.7.4 falla con bcrypt ≥ 4.1. |
| `fetch` nativo sobre axios | No aporta nada que necesitemos. |
| React 18, Tailwind v3 | Ecosistema compatible sin fricción. |
| Blanco y negro sin acento | El problema era el contraste bajo, no la falta de color. |

---

## Próximos pasos

1. **Ver una prueba sobre persona con éxito de punta a punta** (limitación
   #42): con `HF_TOKEN` de una cuenta gratuita en `backend/.env`.
2. **Acabados sin IA generativa, gratis**: mapas de relieve y de brillo por
   tela, calculados desde su mosaico —como los configuradores profesionales—.
   El usuario descartó pagar Fal.ai o Replicate.
3. **Rematar el escote en el croquis** (limitación #36). El analizador de
   personas del probador está entrenado con fotos; habría que medir si
   reconoce la piel de una figura dibujada antes de usarlo ahí.
4. **Fotografiar telas reales.** Un cuadrado limpio de cada rollo mejora el
   resultado más que cualquier ajuste del motor, y es gratis.
5. **Probar con prendas, bocetos y personas reales de un taller.** Lo que hay
   está medido contra ocho prendas y dos fotos de persona.
6. **La conversión prueba→compra.** El Vision Board la pone como métrica y hoy
   no se mide nada. Un botón de «pedir esta tela» con su referencia sería el
   primer paso, y cierra el círculo del producto.
7. **Acceso con Google**, que el usuario ya pidió. De paso resuelve la #14.
