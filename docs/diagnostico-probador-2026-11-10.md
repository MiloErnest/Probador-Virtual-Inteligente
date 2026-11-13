# Diagnóstico del probador sobre personas — 10 de noviembre de 2026

> **Actualizado el mismo día:** después de este diagnóstico sí se cambió el código.
> Lo que se midió y lo que se hizo está al final, en el apartado 7. Lo que sigue
> hasta ahí es el diagnóstico tal como se escribió, antes de tocar nada.

Estado del probador (la foto de una persona con una prenda del taller puesta) y
qué mejorar, antes de tocar nada. **No se ha cambiado código.** Todo lo de aquí
se midió sin llamar a Hugging Face: sobre las dos pruebas reales que guarda la
base de datos, con el analizador local y las funciones del propio probador.

> La muestra es pequeña: dos pruebas y tres fotos. Las conclusiones son un punto
> de partida para medir con un banco fijo (ver «Plan»), no un veredicto.

El script y las hojas comparativas (llevan fotos de personas, por eso no están en
el repositorio) quedan en `Trello-TRAMA\diagnostico-probador\`.

---

## 1. Cómo funciona hoy

```
foto de la persona ──► partes.py   analizador SegFormer B2 (ATR, 18 clases, ONNX cuantizado, CPU)
                  └──► vestir.py   encuadra a la persona en 2:3, con un 6 % de aire
prenda del taller ───► prenda.py   la prenda sobre blanco, recortada a su caja
                       fashn.py    FASHN VTON 1.5 en su Space gratuito (ZeroGPU)
                                   flat-lay · 30 pasos · guía 1,5 · semilla 42 + id · borra la prenda vieja
                       conservar.py del resultado solo entra la ropa de la categoría (en la foto Y en el
                                   resultado) y la prenda vieja que el analizador no vio; lo demás vuelve
                                   a ser la foto original, con un margen de 0,6 % y una pluma de 0,3 %
                       vestir.py   mezcla y pega el recorte en la foto completa
```

Lo que dice el Space de FASHN de sí mismo (leído hoy con `view_api`, sin gastar
cuota): `num_timesteps` 50 por defecto, `guidance_scale` 1,5, `garment_photo_type`
`model` o `flat-lay`, `segmentation_free` verdadero por defecto. El proyecto usa
**30 pasos** (`VTO_STEPS`) y **siempre `flat-lay`**.

## 2. Lo que hay guardado

| Prueba | Fecha | Prenda | Foto | Tiempo | Aviso que dio |
|---|---|---|---|---|---|
| 22 | 30/09 | vestido largo con abertura, estampado floral (categoría completa) | mujer frente a un espejo, cuerpo entero, móvil delante del pecho | 38 s | cambió un 3 % fuera de la prenda |
| 24 | 08/10 | camiseta roja de manga corta (arriba) | hombre en exterior, medio cuerpo, camiseta negra | 36 s | cambió un 13 % fuera de la prenda |

## 3. Lo medido

**Resolución.** El modelo genera a 576 × 864 px. En las dos pruebas su salida se
amplía ×1,48 y ×1,51 para volver a la foto: algo más de la mitad de los píxeles
de la zona generada son interpolados.

**Nitidez** (media del valor absoluto del laplaciano). En la prueba 24 la prenda
generada tiene **1,55**, frente a **4,29** del resto de la foto y 3,50 de la
camiseta original: menos de la mitad del detalle fino. Es lo que hace que se vea
«pegada». En la 22 el estampado floral domina la medida y no sirve para comparar.

**Encuadre.** En la prueba 22, una foto de cuerpo entero, la persona ocupa el 38 %
del ancho del recorte: **220 de los 576 px** con que trabaja el modelo, y el
vestido entero tiene que caber ahí. En la 24, de medio cuerpo, ocupa 558 px. La
foto 2, sin prueba, daría 194 px.

**Qué cambió el modelo**, según el analizador:

- Prueba 24: el **61 % de la piel** de la foto cambió y el **51 % acabó siendo
  ropa**: el modelo le puso **mangas largas verdes** a una camiseta de manga
  corta, y `conservar.py` las dejó entrar porque en el resultado «son ropa».
  También inventó un collar sobre la camiseta (dentro de la prenda: no se puede
  quitar con la regla actual). Del total de lo cambiado, un 11 % era fondo: donde
  la camiseta negra era más ancha que la nueva, el modelo pintó un fondo claro que
  no empalma con el de la foto (la mancha blanca junto al brazo).
- Prueba 22: el vestido salió **mucho más corto** que la prenda (largo hasta los
  tobillos en la prenda, minivestido en el resultado) y el estampado **cubre parte
  del móvil** que la persona sostiene delante.

**El analizador** etiquetó bien a las dos personas de las pruebas (pelo, cara,
brazos, ropa de arriba y de abajo, sin manchas sueltas). No es, con lo visto, la causa principal.

## 4. Dónde está el problema

Contribuyen las tres cosas que se querían separar, y no por igual:

| Parte | Peso | Qué aporta al problema |
|---|---|---|
| **El modelo** (FASHN VTON 1.5 en el Space gratuito) | Alto, pone el techo | Trabaja a 576 × 864 y no se le puede pedir más. Inventa: mangas, collares, cordones (ya visto el 28/09), largo distinto. No es cuestión de instrucciones: no las acepta. |
| **Nuestra composición** (`conservar.py`, `vestir.py`) | Alto, y es lo más barato de mejorar | Deja entrar todo lo que el analizador llama ropa en el resultado, también lo inventado. Donde la prenda vieja era más grande, toma el fondo que inventó el modelo. No iguala la nitidez de la zona con la de la foto. |
| **El encuadre** (`vestir.py`) | Medio | Es el mismo para todas las categorías: en una foto de cuerpo entero, una prenda de arriba recibe muy pocos píxeles del modelo. |
| **Los parámetros** (`fashn.py`) | Sin medir | 30 pasos frente a los 50 del modelo; siempre `flat-lay`, aunque la prenda del taller puede venir de una foto con alguien puesto. |
| **Las fotos de entrada** | Medio | Espejos con objetos delante del cuerpo, retratos muy estrechos (la foto de la prueba 24 es 0,56 de ancho/alto; el modelo trabaja a 0,67). |

Hay además un obstáculo de método: **no se guarda lo que devuelve el modelo**,
solo el resultado ya compuesto. Cualquier ajuste de la composición obliga a
repetir la prueba con el modelo, y la cuota de ZeroGPU es de pocas pruebas al día.

## 5. Recomendaciones, en orden

0. **Guardar la salida cruda del modelo y sus parámetros** en cada prueba
   (historia propuesta Ep11-Hu8). Es pequeño, no cambia lo que ve el usuario y
   permite iterar la composición gratis y sin red.
1. **Un banco fijo** (Ep11-Hu6, ya en el backlog): unas 6 fotos (de pie, sentada,
   espejo, medio cuerpo, cuerpo entero, brazos cruzados) × 3 prendas (arriba,
   abajo, completa), con métricas automáticas: nitidez relativa, fracción
   descartada, piel convertida en ropa, píxeles de persona en la entrada. Cada
   cambio se mide contra él.
2. **Composición que no se deje engañar** (Ep11-Hu10): lo que el resultado llama
   ropa pero no se parece a los colores de la prenda vuelve a ser la foto; las
   manos y lo que sostienen conservan sus píxeles; el fondo que aparece donde
   estaba la prenda vieja se reconstruye desde la foto (un *inpainting* local
   basta para franjas finas) en vez de tomar el del modelo.
3. **Encuadre por categoría** (Ep11-Hu9): para una prenda de arriba, de la cabeza a
   la cadera.
4. **Nitidez** (Ep11-Hu11): igualar el grano y el detalle de la zona generada con
   el de la foto, sin tocar forma ni color.
5. **30 o 50 pasos, con datos** (Ep11-Hu12).
6. **Solo si con todo eso no basta, cambiar de modelo.** El contrato
   `ModeloDePrueba` ya permite añadir otro proveedor sin tocar el resto, y el
   banco dirá si el cambio compensa. Ojo con las licencias (IDM-VTON y CatVTON no
   son comerciales; valen para el proyecto universitario) y con el coste: la
   preferencia del equipo es la vía gratuita.

## 6. Lo que no se tocó

Ni el código del probador ni su configuración. Tampoco se lanzó ninguna prueba
nueva contra Hugging Face: solo se leyó la descripción de la API del Space.

---

## 7. Lo que se hizo después, el mismo día

El usuario pidió arreglar todo lo posible. Se hicieron ocho pruebas reales con el
modelo, guardando cada vez lo que devolvía, y con esas salidas se ajustó la
composición sin volver a gastar cuota.

### Lo que este diagnóstico acertó y lo que no

| Lo que decía | Lo que salió al medir |
|---|---|
| El modelo inventa mangas y no se le puede decir que no | Cierto, y depende de la semilla: con la 66 salen las mangas verdes (en los dos modos, con 30 y 50 pasos); con la 70, no. |
| El vestido sale más corto que la prenda, por culpa del modelo | **Era cómo se le llamaba.** En el modo que borra la prenda vieja, la nueva queda recortada a su hueco. Sin borrar, llega a los tobillos y el móvil no se pinta. |
| 30 o 50 pasos, «sin medir» | A 30 pasos el vestido sale con dos agujeros en las rodillas; a 50, entero. Misma foto, prenda y semilla. |
| El fondo claro junto al brazo no empalma | Cierto, y era nuestro: se copiaba el fondo que regenera el modelo. También el ribete claro de toda la prenda. |
| La prenda tiene menos de la mitad del detalle fino; hay que igualar la nitidez | **Falso.** Las fotos no tienen grano (0,25 sobre 255) y una prenda estampada da más detalle que el resto (17,7 frente a 4,3). La camiseta era lisa. No se cambió nada. |
| El encuadre da pocos píxeles a una prenda de arriba | Cierto: 193 y 220 px de ancho para la persona. Con el encuadre por prenda, 318 y 338. |
| No se guarda la salida del modelo | Cierto, y era lo que más frenaba. Ahora se guarda con cada prueba. |

### Lo que cambió en el código

| Archivo | Cambio |
|---|---|
| `app/probador/fashn.py`, `app/core/config.py` | Sin borrar la prenda vieja y con 50 pasos. `VTO_ERASE_FIRST=true` vuelve atrás. |
| `app/probador/conservar.py` | El fondo es siempre el de la foto, continuado donde lo tapaba la prenda vieja. La ropa que no tiene los colores de la prenda no entra donde tapaba piel. Lo que la persona sostiene no cuenta como fondo. |
| `app/probador/vestir.py` | Encuadre de la cabeza a medio muslo para una prenda de arriba. `recomponer`: la composición sola, sin modelo. Avisos nuevos. |
| `app/models/try_on.py`, migración `3a17a80c22fb`, `app/services/try_on.py` | Cada prueba guarda la salida cruda, su caja y los parámetros. |
| `scripts/recomponer.py` | Rehace la composición de las pruebas guardadas, sin cuota. |
| `tests/test_probador.py` | Ocho tests nuevos, uno por defecto encontrado. |

### Las prendas generadas de bocetos

Era la primera vez que se probaban sobre una persona, y funcionan: la chaqueta
corta sobre una foto de cuerpo entero frente a un espejo, y el vestido de noche
sobre otra. Con sus límites, vistos en esa única prueba del vestido: el modelo lo
dibuja largo y con vuelo, pero termina en los tobillos —la cola del boceto no
sale— y simplifica el escote a un palabra de honor recto, sin la banda caída
sobre los hombros.

### Lo que sigue sin resolver

- Lo que el modelo inventa DENTRO de la prenda (un collar, un cinturón), y la
  ropa inventada del mismo color que la prenda.
- Restos de la prenda vieja al pasar de manga larga a corta: no se ha medido,
  porque ninguna foto llevaba manga larga.
- El encuadre para prendas de abajo: no había ninguna con la que medirlo.
- El techo del modelo, 576 × 864 px.

Las salidas crudas de las ocho pruebas, las hojas comparativas y los scripts con
los que se midió están en `Trello-TRAMA\diagnostico-probador\`, fuera del
repositorio porque llevan fotos de personas.

---

## 8. Dos días después, el 12/11/2026: los brazos y el vestido de noche

El usuario probó tres prendas más (pruebas 30, 31 y 32) y encontró dos cosas.
Las dos se midieron sobre la salida cruda que ya guarda cada prueba.

### Los brazos: arreglado

Queja: con una camiseta gris, a un hombre musculoso «pareciera que le quitáramos
masa muscular». Medido en la prueba 30: el modelo dibuja el antebrazo con el
borde de fuera en su sitio, pero mucho más fino, y el hueco que deja por dentro
lo llena con camiseta. Como eso «es ropa», nuestra composición lo ponía encima
del brazo de la foto.

Ahora, en los tramos del brazo que la imagen generada deja al aire, el brazo de
la foto se queda entero (`_brazos_al_aire`, en `conservar.py`). El corte con la
manga sigue el dobladillo que dibujó el modelo. Dos tests nuevos, 127 en total;
las pruebas 25, 30, 31 y 32 se recompusieron sin gastar cuota (la 30 cambia un
2,1 % de la foto; las otras, 0,1–0,2 %).

Se descartó, midiéndolo, deformar la imagen del modelo hasta la silueta de la
foto: el contorno exterior casi no se mueve (0,6 px); lo que cambia es por dentro.

Lo que no se arregla: la prenda cae holgada sobre un torso que el modelo dibuja
más estrecho. Eso es dibujo suyo.

### El vestido de noche: no arreglado, y no es cuestión de parámetros

Queja: el vestido generado de un boceto «no cumple con las medidas» al probarse.
El vestido tiene hombros caídos con drapeado, corte sirena y sobrefalda con cola;
el modelo devuelve siempre un palabra de honor en línea A a media pierna.

Misma foto y misma semilla, cuatro configuraciones:

| Configuración | Resultado |
|---|---|
| `flat-lay`, guía 1,5 (la de siempre) | Palabra de honor, línea A, media pierna |
| Tipo de foto `model` | Igual |
| Guía 2,5 | Igual, y con restos de la camiseta vieja |
| Prenda estirada ×1,3 a lo alto | Igual |

También se probó un prototipo que coloca la imagen de la prenda encima con su
forma exacta. Se ve pegada y tapa los muebles: una imagen plana no sabe qué hay
delante de ella.

Y de paso salió por qué «tal cual» no puede ser, con ningún modelo: el vestido
del boceto tiene proporciones de figurín. De la cintura al bajo mide 7,9 veces el
ancho de la cintura; en una persona son unas 3,7.

Lo que queda es medir otro modelo de prueba virtual, gratuito, con este mismo
vestido. `ModeloDePrueba` permite añadirlo sin tocar el resto.
