# Estado del proyecto

> Documento vivo. Se actualiza al cerrar cada etapa.

**Etapa actual:** probador con cámara, sin IA. Reestructuración completa.
**Última actualización:** 2026-09-14

---

## Qué pasó el 2026-09-14

Se retiró **toda la IA generativa** y la aplicación se redujo a lo que el
usuario quería que hiciera: vestir a alguien delante de la cámara.

**Por qué.** Las Fases 1, 2 y 3 estaban construidas de punta a punta, pero con
proveedores simulados: un probador que pegaba la prenda con Pillow, un
generador de diseños que dibujaba siluetas según palabras clave, y un análisis
corporal que estimaba medidas a partir de la altura. Todo funcionaba y nada
convencía. Y el problema de verdad —que la prenda no encajaba sobre el
cuerpo— seguía intacto, porque el esfuerzo se repartía entre cinco fases.

**Qué se borró.**

| Se fue | Dónde vivía |
|---|---|
| Probador por foto con IA (local y Gemini) | `app/ai/`, `try_on_sessions`, `TryOnPage` |
| Generador de diseños por texto | `app/ai/design_provider.py`, `designs`, `DesignAIPage` |
| Análisis corporal y recomendación de talla | `app/vision/`, `body_profiles`, `BodyProfilePage` |
| Maniquí 3D con Three.js | `frontend/src/ar/avatar3d.ts` |
| Historial de pruebas | `MyTryOnsPage` |
| `google-genai`, `three`, `@types/three` | requisitos del backend y del frontend |

La migración `1a61ba91aea8` tira las tres tablas. **Borra datos a propósito**:
el historial de pruebas y los diseños guardados desaparecen. Su `downgrade`
reconstruye las tablas vacías — recupera el esquema, no el contenido.

**Qué se ganó.** 217 KB de bundle en lugar de ~800 KB. Un backend con cuatro
rutas. Y un probador que ya no es el borrador de otra cosa.

---

## Lo que funciona

### El probador (es la aplicación)

- [x] Cámara + MediaPipe Pose en WebAssembly, **entero en el navegador**.
      Ninguna imagen de la persona llega al servidor: no es que se borre
      después, es que no se envía.
- [x] Recorte del fondo de la prenda por relleno desde los bordes, con umbral
      adaptativo y cierre morfológico (`removeBackground.ts`).
- [x] **Medidas reales del cuerpo**, con la corrección anatómica entre la
      articulación que detecta el modelo y el borde exterior del cuerpo.
- [x] **Contorno real medido sobre la máscara de segmentación**, a 28 alturas
      a lo largo del tramo que cubre la prenda.
- [x] **Deformación por franjas**: la prenda se parte en 28 tiras y cada una
      sigue el eje del cuerpo, con su ancho, su posición y su inclinación.
      Dobla por la rodilla en un pantalón y gira si te inclinas.
- [x] Anclaje por categoría: camiseta de hombros a bajo cadera, pantalón de
      cintura a tobillo, vestido hasta la rodilla, chaqueta algo más larga. Y
      el tamaño de la prenda sale de ese tramo, no de medir su anchura.
- [x] Suavizado temporal de las medidas, **por constante de tiempo real**: el
      comportamiento ya no depende de los fotogramas por segundo.
- [x] **Inercia**: la prenda va por detrás de ti y rebota al parar, con un
      muelle amortiguado de paso fijo (1/120 s). El tejido decide cuánto.
- [x] **Orientación 3D**: la tela rueda alrededor del cuerpo al girarte y se
      desvanece cuando ya no queda frente que enseñar. De espaldas no se
      dibuja, porque del reverso no hay fotografía.
- [x] Recorte opcional contra la silueta engordada, para que la prenda no
      flote sobre el fondo sin perder la holgura.
- [x] Guías de detección (silueta + esqueleto) conmutables.
- [x] Ajuste fino manual de ancho, largo y altura, para lo que una categoría
      no distingue (una chaqueta y un abrigo largo son ambos «abrigos»).
- [x] **Aviso cuando el recorte de una fotografía sale roto**, en vez de
      dibujar la prenda a tiras sin decir nada.
- [x] Entrada directa desde el catálogo con `/probador?prenda=12`.

### Tejido de la prenda

- [x] Columna `fabric` en `garments`, nullable, con ocho valores.
- [x] Cada tejido define **ceñido** (cuánto adopta la forma del cuerpo) y
      **holgura** (cuánto más ancho cae). El cuero mantiene su forma; el punto
      se pega.
- [x] Y desde la inercia, también **masa**: frecuencia propia, amortiguación y
      vuelo. Medido sobre un salto de 100 px — cuero: 0 px de rebote, asentado
      en 0,30 s; seda: 36,7 px de rebote y 1,03 s. Sigue sin ser simulación de
      tela: es un muelle por prenda, no una malla con hilos.
- [x] Se puede cambiar en vivo desde el probador para comparar.
- [x] Una prenda sin tejido registrado dice que no lo tiene. No se inventa un
      valor por defecto, y hay una prueba que lo fija.

### Backend

- [x] FastAPI con CORS por entorno y configuración por variables de entorno.
- [x] PostgreSQL con SQLAlchemy 2.0 síncrono. Esquema gobernado por Alembic.
- [x] `GET /api/health` que informa también del estado de la base de datos.
- [x] Registro con bcrypt, login JWT, `GET /api/auth/me`.
- [x] Catálogo: listar con filtro por categoría, obtener, crear, subir imagen.
- [x] Validación de imágenes por CONTENIDO con Pillow, no por `Content-Type`.
- [x] Costura `Storage` con implementación en disco local y servido en `/media`.
- [x] Semilla idempotente, con las cinco fotografías reales del repositorio.
- [x] **53 pruebas automatizadas, ejecutadas y en verde.**

### Frontend

- [x] React 18 + TypeScript + Vite + Tailwind. Build de producción verificado.
- [x] Sesión con `AuthContext`, formularios de acceso y registro, rutas
      protegidas.
- [x] Cinco pantallas: portada, catálogo, probador, acceso/registro, perfil.
- [x] Rediseño completo en blanco y negro (ver más abajo).

---

## Verificación hecha el 2026-09-14

**Backend.** `pytest` → 53 en verde. `alembic upgrade head` aplicado sobre la
base real. `alembic check` → "No new upgrade operations detected". Arranque con
uvicorn correcto, `/api/garments` devuelve las 13 prendas con su tejido.

**Frontend.** `tsc --noEmit` limpio. `npm run build` correcto (217 KB).
Consola del navegador sin errores. Archivos de MediaPipe servidos: el modelo
(5,6 MB) y el wasm (11,5 MB) responden 200.

**El encaje, sin cámara.** Se importó `vestir.ts` desde la consola del
navegador, se construyó un cuerpo sintético con proporciones antropométricas
reales y se pasaron por él las cinco fotografías del catálogo, recortadas por
el mismo código que usa la aplicación. Se midieron los píxeles pintados.

Cuerpo de referencia: hombros en y=200, caderas en y=420 (torso 220 px),
rodillas 616, tobillos 812. Ancho real de hombros 214 px, de caderas 182 px.

| Prenda | Ancho | Acaba en | Lectura |
|---|---|---|---|
| Jersey gris (top, punto) | 249 px · 1,16× hombros | 66 px bajo la cadera | ✅ |
| Camiseta blanca (top, algodón) | 233 px · 1,09× | 66 px bajo la cadera | ✅ colocación; ❌ recorte |
| Camisa marrón (top, algodón) | 225 px · 1,05× | 66 px bajo la cadera | ✅ |
| Chaqueta de cuero (abrigo) | 328 px · 1,53× | 88 px bajo la cadera | ✅ |
| Vaquero (inferior, denim) | 180 px ≈ ancho de cadera | exactamente en el tobillo | ✅ |

Sin ver las piernas, el vaquero acaba 26 px por debajo del tobillo real: la
proporción media de reserva se equivoca en un 3% del largo de la pierna.

Con el cuerpo inclinado, el centro de la prenda sigue al del cuerpo con 7–11 px
de desvío sobre un torso de 220 px. Con las piernas quebradas, el centro del
pantalón se desplaza hacia la rodilla y vuelve hacia el tobillo.

El contorno medido sobre una máscara sintética detecta el pellizco de la
cintura en la fila exacta donde se puso, y a la altura de las rodillas mide las
dos perneras pese al hueco que hay entre ellas.

**Tres errores encontrados así, antes de tocar la cámara.** Los tres habrían
pasado por buenos a ojo:

1. El camino del pantalón se pasaba 148 px del tobillo, porque el final
   teórico se añadía aunque el modelo ya hubiera visto el tobillo. Y el del
   vestido se saltaba la rodilla por lo mismo al revés. Ahora manda el punto
   que el modelo ve, y la distancia teórica es solo el plan B.
2. Cada franja leía el ancho del cuerpo por su número de fila, no por la
   altura a la que caía. Una camiseta no cubre el tramo entero que se le
   reserva, así que su bajo se ajustaba a un ancho medido más abajo.
3. **El tamaño se calculaba igualando el ancho de la prenda al del cuerpo, y
   esa medida no es de fiar.** Ver la decisión correspondiente más abajo. Es
   el cambio de fondo de esta etapa.

**La cámara arranca.** Verificado por el usuario en Chrome, sobre
`localhost:5173`, después de arreglar el fallo de abajo. Lo que sigue sin
comprobarse es la CALIDAD del encaje sobre una persona real (limitación #24).

**Un cuarto error, este encontrado al usarlo.** Al pulsar «Encender» la
pantalla volvía al mismo botón sin decir nada, pasara lo que pasara. El
`catch` del arranque hacía `setStatus('error')` y a continuación `stop()`, que
acaba en `setStatus('idle')`: React agrupa los cambios de estado y gana el
último, así que **el estado de error se perdía siempre**. Ni mensaje dentro del
recuadro, ni botón de reintentar.

Arreglado separando la limpieza (`soltarTodo`) del cambio de estado. Y de paso,
tres cosas más que salieron al mirarlo:

- **La cámara se pide ahora ANTES de cargar el modelo.** Antes esperabas ~28 MB
  de descarga antes de que el navegador te preguntara siquiera por el permiso,
  y ese silencio se parecía mucho a «el botón no hace nada».
- **Si la GPU falla, se reintenta en CPU.** Medido en este equipo: GPU 3,2 s,
  CPU 0,7 s, las dos correctas — pero hay equipos sin aceleración por hardware
  donde solo funciona la segunda, y antes ahí no arrancaba.
- El motivo del fallo se repite **dentro del recuadro negro**, que es donde
  está la mirada cuando la cámara no tira, y los mensajes distinguen permiso
  bloqueado, cámara ocupada por otro programa, equipo sin cámara y dirección no
  permitida (abrirlo por la IP de la red local, no por `localhost`).

---

## Errores conocidos y limitaciones

| # | Descripción | Impacto | Plan |
|---|---|---|---|
| 24 | **El encaje no se ha probado con una cámara y una persona de verdad.** La cámara ya arranca y se ve la imagen; lo que falta es juzgar si la prenda queda bien puesta. La geometría está verificada con cuerpos sintéticos, que no tiemblan, no se giran y tienen una máscara perfecta. | Alto | Es lo primero que hay que hacer. Si algo baila, el sitio es `suavizarCuerpo`; si la talla no cuadra, `TRAMOS[categoria].referencia`. |
| 25 | **No hay oclusión.** Si pones la mano delante del pecho, la prenda te tapa la mano. El navegador sabe qué píxeles son persona, pero no cuáles están delante. | Medio | Se puede aproximar recortando los antebrazos cuando cruzan el torso. No es gratis y aún no se ha intentado. |
| 26 | **No hay simulación de tela.** Ni pliegues, ni sombras propias, ni peso. Una camisa no ondea. La interfaz lo dice en la portada y en el probador. | Medio | Es la Fase 3D. Necesita motor y materiales; el campo `fabric` ya está puesto para cuando llegue. |
| 27 | **La camiseta blanca del catálogo NO se puede recortar, y no es cuestión de ajustar nada.** Medido: el fondo es (217,218,212) y hay zonas de tela en sombra que valen exactamente (217,217,217) — distancia 6, cuando el propio fondo varía 7 a lo largo del borde. La tela y el fondo son el mismo color. Se dibuja a tiras. | Alto | **La aplicación lo detecta y avisa** (`recorteDudoso`), así que no se confunde con un fallo del encaje. La solución es una fotografía sobre fondo que contraste. Un recorte de calidad real es trabajo de un modelo de segmentación. |
| 28 | **Las ocho prendas de la semilla son siluetas planas de colores**, dibujadas con Pillow. En el catálogo, al lado de las cinco fotografías reales, se ven mal. | Bajo | Retirarlas con `active = false`, o subirles fotos reales. Es decisión del usuario: son sus datos. |
| 29 | **Hace falta salir de cabeza a cadera en el encuadre.** Con un portátil sobre la mesa no siempre se consigue, y sin los cuatro puntos clave no se dibuja nada. | Medio | La pantalla lo avisa. Un aviso más concreto ("acércate", "apártate") sería fácil de añadir. |
| 4 | Los tests usan SQLite, no PostgreSQL. No validan comportamiento específico de PG. | Medio | Aceptable mientras el esquema sea portable. |
| 5 | **El proyecto está dentro de OneDrive.** `node_modules` y `.venv` provocan sincronización constante. | Medio | Mover a `C:\dev\` o excluir esas carpetas de OneDrive. |
| 20 | **Las imágenes de Docker nunca se han construido.** Solo se validó la sintaxis del compose. | Medio | `docker compose --profile full up -d --build` con Docker Desktop arrancado. |
| 7 | Las imágenes se sirven desde el proceso de FastAPI. | Bajo | Delegar en Nginx/CDN cuando haya despliegue real. |
| 8 | Sin límite de peticiones. **Incluye el login**: nada impide probar contraseñas en bucle. | Medio | Antes de exponer la aplicación públicamente. `slowapi` o un límite en el proxy. |
| 9 | **Sin refresh token ni lista de revocación.** Cerrar sesión descarta el token en el navegador, pero seguiría siendo válido hasta caducar (12 h). | Bajo | Solo si aparece la necesidad real de expulsar a alguien al momento. |
| 10 | **El token se guarda en `localStorage`.** Un fallo de XSS permitiría leerlo. Se aceptó a cambio de que recargar no cierre la sesión. | Medio | Primer punto a revisar antes de un despliegue público. |
| 11 | **Cualquier usuario registrado puede dar de alta prendas.** No existe la distinción usuario/administrador. | Bajo | Columna `is_admin` cuando haya un panel que la justifique. |
| 12 | **Las migraciones no se ejecutan en los tests**, que crean el esquema desde los modelos con SQLite. | Medio | Se contrastan a mano con `alembic check`. |
| 14 | **El registro no verifica que el buzón exista.** No hay correo de confirmación. | Medio | Se resolverá con el acceso mediante Google. |
| 13 | La suite tarda ~24 s. Es bcrypt, que es lento a propósito. | Bajo | Aceptable. Si molesta, bajar el coste de bcrypt solo en el entorno de test. |

---

## Decisiones técnicas

### De la reestructuración (2026-09-14)

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| **Retirar la IA en lugar de seguir mejorándola** | Conectar Gemini de verdad | Los proveedores simulados ya no aportaban, y los reales cuestan dinero por imagen. Pero el motivo de fondo es otro: mientras el probador fuera el borrador que se enviaba al modelo, no había presión para que la superposición estuviera bien hecha. Quitando el modelo, la superposición es el producto. |
| **Borrar las tablas en vez de dejarlas** | Mantenerlas "por si acaso" | Ya no hay código que sepa leerlas. Quedarían datos huérfanos que nadie miraría y que aparecerían en cada `alembic check`. |
| **Borrar también el maniquí 3D** | Desengancharlo del perfil corporal y conservarlo | Decisión del usuario. Dependía de las medidas del perfil corporal, que se iba, y un maniquí con una textura plana encima tampoco vestía bien. Los 600 KB de Three.js volverán cuando haya telas de verdad que simular. |
| **El login se queda delante del probador** | Abrirlo, ya que no envía nada al servidor | Decisión del usuario: quiere controlar el flujo de usuarios y más adelante entrar con Google. |
| **El tamaño de la prenda sale de su ALTO** | Igualar su ANCHO al del cuerpo | Es el cambio de fondo de esta etapa, y se llegó a él descartando lo otro con medidas. Escalar por el ancho respeta la proporción de la foto, que suena mejor; con las fotos reales da resultados incoherentes, porque el ancho de una foto de producto depende de cómo esté colocada la prenda y de qué tal haya salido el recorte. La camiseta blanca, con un agujero en el torso, se medía un 35% estrecha y se dibujaba a mitad del muslo; la camisa marrón, con las mangas tocando el torso, medía la prenda entera en la fila del pecho y salía por encima de la cadera. Se probaron tres formas de medir ese ancho —de borde a borde, solo la mancha central, y por franjas según la categoría— y ninguna aguanta las cinco fotos. El alto no tiene ese problema: una camiseta empieza en el hombro y acaba en el bajo, y eso es cierto en todas las fotos. |
| **Un control manual de largo** | Deducir el largo de la proporción de la foto | Al anclar por alto, la categoría decide el largo, y una categoría mete en el mismo saco una chaqueta biker y un abrigo hasta la rodilla. La foto ya no puede desempatar —por lo de arriba—, así que la salida es un control. Son tres líneas y resuelve un caso conocido. |
| **Avisar cuando el recorte sale roto** | Dibujarlo igual | Antes se pintaba la camiseta a tiras sin decir nada, y quien la veía no podía saber si el fallo era del recorte, del encaje o de la cámara. La métrica (borde respecto a superficie, más cobertura) separa las cuatro fotos buenas —0,011 a 0,020— de la rota, 0,031. |
| **Corrección anatómica en los puntos de MediaPipe** | Un multiplicador ajustable a ojo | El `1.9` anterior había que reajustarlo por cada foto y cada persona porque mezclaba dos correcciones distintas: la anatómica (constante para todos) y el encuadre de la foto (propio de cada una). Separadas, la primera es un factor fijo y la segunda sale del recorte. |
| **Franjas horizontales** | Malla de triángulos | `drawImage` solo hace transformaciones afines sobre rectángulos. Una malla obliga a recortar triángulo a triángulo: más código, más coste y costuras dentadas. Veintiocho trapecios describen la misma curva. |
| **La máscara corrige, no decide** | Confiar en el contorno medido | Con los brazos pegados al cuerpo, el barrido los incluye y la prenda saldría ancha; con un fondo complicado, la segmentación se rompe. Limitando la corrección, un fallo deforma un poco en lugar de arruinarlo todo. |
| **El barrido guarda el punto más lejano, no el primer hueco** | Parar en el primer píxel de fondo | Un pantalón cubre dos piernas y entre ellas hay fondo. Parando en el primer hueco, a la altura de las rodillas mediría cero. |
| **Dibujar en un lienzo aparte y volcarlo** | Pintar las franjas directamente | Las franjas se solapan un píxel para que no se vea la costura. Con transparencia, ese píxel se pintaría dos veces y cada unión saldría como una raya oscura. |
| **Recorte contra la silueta ENGORDADA** | Contra la silueta exacta | Recortar por el borde del cuerpo convertiría la ropa en pintura corporal: una chaqueta holgada tiene que sobresalir. Lo que molesta es verla flotar sobre el fondo. |
| **Suavizado exponencial con salto detectado** | Suavizar siempre | El modelo reestima la pose en cada fotograma y los puntos bailan. Pero suavizar un salto grande —la persona se movió de verdad— dejaría la prenda arrastrándose por la pantalla. |
| **`fabric` nullable sin valor por defecto** | Poner "algodón" a lo existente | Del tejido depende el encaje. Rellenarlo con un valor inventado se vería en pantalla y nadie sabría de dónde salió. |
| **Blanco y negro sin color de acento** | Añadir más color | El usuario dijo que se veía "pálido". El problema no era la falta de color sino el contraste bajo en toda la página. Los extremos lo arreglan, y a un catálogo de ropa le va mejor. |
| **Los estados no se distinguen por color** | Semáforo verde/ámbar/rojo | En una página sin color, tres puntos coloreados serían lo único llamativo, y el tema de la página no es el estado del servidor. Por forma y por palabra funciona además para quien no distingue el rojo del verde. |

### Anteriores, todavía vigentes

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| Monolito modular por capas | Microservicios | Con un dominio aún poco conocido, los límites de servicio se pondrían mal. |
| SQLAlchemy síncrono | `AsyncSession` | Consultas triviales; el modo síncrono es más simple de depurar y testear. |
| Migración inicial generada contra una base vacía desechable | Autogenerar contra `vfit` | Contra una base que ya tenía las tablas habría producido una migración VACÍA. |
| `create_all` fuera del arranque | Dejarlo "por si acaso" | Dos fuentes de verdad para el esquema divergen en silencio. |
| `compare_type` y `compare_server_default` activos | Los valores por defecto de Alembic | Sin ellos, autogenerate se pierde los cambios de tipo, que son los más habituales. |
| `PyJWT` | `python-jose` | python-jose tiene mantenimiento irregular e historial de CVEs. |
| HS256 fijado en código | Algoritmo configurable por entorno | Un algoritmo elegido por configuración se puede degradar a `none`. |
| Login con JSON | `OAuth2PasswordRequestForm` | El formulario obliga a enviar un campo `username` que en realidad contiene un email. |
| Token en `localStorage` | Solo en memoria; cookie `httpOnly` | En memoria, cada recarga cierra la sesión. La cookie exige CSRF y cookies entre orígenes. |
| Validar el token guardado contra `/auth/me` al arrancar | Confiar en él | Un token caducado pintaría la interfaz como "sesión iniciada" con todas las peticiones fallando. |
| 404 en recursos ajenos | 403 | Un 403 confirma que el recurso existe. |
| Sin `POST /auth/logout` | Endpoint de cierre de sesión | Sin lista de revocación no podría invalidar nada: fingiría trabajar. |
| **Seguir siendo aplicación web** | Empaquetar en un `.exe` | Lo descartó el usuario el 2026-09-06. Un instalador obliga a abandonar PostgreSQL. **No reabrir sin que lo pida.** |
| `image_key` en BD, `image_url` en la API | Guardar la URL completa | Migrar a S3/R2 no obliga a reescribir filas. |
| Enums como `VARCHAR` sin CHECK | `ENUM` nativo de PostgreSQL | Añadir un valor a un ENUM nativo exige `ALTER TYPE`; estas listas crecen. Los valores los valida Pydantic. |
| `bcrypt` directo | `passlib[bcrypt]` | passlib 1.7.4 falla con bcrypt ≥ 4.1 y no tiene mantenimiento activo. |
| `max_length=72` en la contraseña | Sin límite | bcrypt trunca en silencio a 72 bytes. |
| `fetch` nativo | axios | No aporta nada que necesitemos. |
| Hook `useApi` propio | TanStack Query | Aún no hay caché ni revalidación que gestionar. |
| React 18 | React 19 | Todo el ecosistema es compatible sin fricción. |
| Tailwind v3 | Tailwind v4 | v4 cambia a configuración CSS-first; casi toda la documentación existente es de v3. |
| PostgreSQL nativo con rol `vfit` dedicado | Usar el superusuario `postgres` | La aplicación no debe correr como superusuario. |
| Docker solo para PostgreSQL | Dockerizar toda la aplicación | El hot-reload nativo es más rápido de depurar en desarrollo. |

---

## Próximos pasos

1. **Probarlo con una cámara y una persona.** Es lo único que falta para dar
   el encaje por bueno. Todo lo demás está medido.
2. **Decidir qué hacer con las ocho prendas de silueta** del catálogo:
   retirarlas o darles fotografías reales.
3. **Ajustar los tramos con lo que se vea.** `TRAMOS` en `vestir.ts` tiene los
   números de dónde empieza y acaba cada categoría, y están comentados uno a
   uno. Cambiarlos es cambiar un número, no reescribir nada.
4. **Acceso con Google**, que el usuario ya ha pedido. De paso resuelve la
   limitación #14: garantiza que el buzón existe.
5. Oclusión de los brazos cuando cruzan el torso (limitación #25), si molesta
   al usarlo de verdad.
