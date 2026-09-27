"""Estampar una tela sobre una prenda conservando sus pliegues reales.

LA IDEA, EN UNA FRASE
---------------------
La fotografía de una prenda ya contiene, gratis, toda la información difícil:
dónde hay un pliegue, dónde da la luz, dónde cae una sombra. Esa información no
depende del color de la prenda —depende de su forma—, así que se puede separar
del color y reutilizarla con otra tela.

POR QUÉ NO BASTA MULTIPLICAR POR EL BRILLO
------------------------------------------
Es el primer intento de todo el mundo y está mal. Si la prenda original es azul
marino, su brillo es bajo en toda la superficie, y multiplicar deja la tela
nueva oscura aunque sea blanca. Si es blanca, el brillo es casi 1 y la tela
sale plana, sin un solo pliegue.

El brillo mezcla dos cosas: **cuánta luz refleja el material** (su color propio)
y **cuánta luz le llega** (la forma). Lo que queremos es lo segundo.

Se separan dividiendo: se mide el brillo típico de la prenda —su color propio—
y se divide el brillo de cada píxel entre él. Lo que queda vale 1 donde la luz
es normal, menos en un pliegue y más en un brillo, **y ya no depende del color
original**. Esa razón es la que se traslada a la tela nueva.

EN LUZ LINEAL, NO EN sRGB
-------------------------
Los valores de un PNG no son proporcionales a la luz: llevan una curva encima
para aprovechar los 256 niveles donde el ojo distingue mejor. Multiplicar sobre
esos números no multiplica luz, y las sombras salen más oscuras de lo que
deberían.

Es el detalle que separa un resultado que «casi cuela» de uno que parece una
fotografía, y cuesta dos funciones. Se deshace la curva, se multiplica, y se
vuelve a poner.

LO QUE ESTE MOTOR NO PUEDE HACER
--------------------------------
No cambia cómo CAE la tela. Si la foto es de un vestido de seda fluida y le
pones una lona rígida, la lona caerá como seda, porque los pliegues son los de
la foto. Para eso haría falta simular el tejido, que es otro problema y mucho
mayor.

UN BOCETO TAMBIÉN TIENE LUZ, Y ESO SE TARDÓ EN VER
---------------------------------------------------
Aquí ponía que un dibujo no tiene sombras y que por eso la tela salía plana.
Es cierto de un plano técnico —línea limpia, sin tonos— y **falso del dibujo
que de verdad hace un diseñador**: un figurín va sombreado a lápiz, y ese
sombreado es exactamente dónde caen los pliegues, cómo se pliega la cola, dónde
la tela se aleja de la luz. Es la misma información que trae una fotografía,
dibujada a mano.

Ignorarla y sustituirla por un degradado desde el borde daba lo que el usuario
describió de una sola frase: **parecía que le hubieran echado pintura a la
prenda**. Y tenía razón — era relleno plano más viñeta.

Lo que hay que separar en un dibujo no es «forma contra color», es **trazo
contra sombreado**: la línea es estrecha y define el diseño, y hay que dejarla
encima intacta; la mancha es ancha y es luz, y va debajo multiplicando la tela.
Ver `_separar_trazo_de_sombreado`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from app.textil.filtros import desenfocar as _desenfocar, maximo_local, reescalar
from app.textil.veta import coordenadas_de_la_veta

#: Pesos de luminancia de la Rec. 709. El ojo no reparte por igual entre los
#: tres canales, y aquí importa porque lo que se mide es luz, no color.
LUMINANCIA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)

#: Hasta dónde se deja llegar la sombra. Un pliegue muy cerrado da razones
#: extremas que, sobre la tela nueva, se ven como manchas negras.
SOMBRA_MINIMA = 0.25

#: Hasta dónde se deja llegar la LUZ, según la tela nueva. Una tela mate no
#: devuelve el brillo del cuero ni del raso que había; una satinada sí.
LUZ_MATE = 1.35
LUZ_SATINADA = 1.9

#: Brillo extra en las crestas de los pliegues de una tela satinada.
BRILLO_SATINADO = 0.25

#: Rango natural de los pliegues, como dispersión del logaritmo del brillo.
#:
#: Medido en el banco de pruebas: camiseta blanca 0,13 (aplastada por la
#: sobreexposición), jersey 0,49 y camisa 0,47 (tono medio, bien capturados),
#: vaquero 0,69, vestido negro 0,73, camiseta negra 0,82, cazadora de cuero
#: 0,92 (hinchados: sobre un casi-negro cada variación es una razón enorme).
#: Se lleva todo hacia el rango de las de tono medio.
FORMA_MINIMA = 0.35
FORMA_MAXIMA = 0.55
#: Cuánto se puede estirar una prenda aplastada. Más, y se estiraría el ruido.
GANANCIA_MAXIMA_DE_FORMA = 2.5

#: Umbral del detalle, en unidades del nivel de textura de la propia prenda.
#: Por debajo es la trama del material viejo; por encima, costuras y botones.
UMBRAL_DE_TEXTURA = 1.5

#: Cuánto detalle fino se conserva de la prenda original, de 0 a 1.
#:
#: El mapa de luz se desenfoca para borrar el TEJIDO de la prenda original
#: —sus hilos, su trama—, que es justo lo que venimos a sustituir. Pero ese
#: mismo desenfoque se lleva por delante las costuras, los botones y los
#: pespuntes, que sí queremos conservar porque son la prenda y no la tela.
#:
#: Con la trama vieja ya quitada por umbral, se puede devolver más detalle que
#: antes (0,35) sin que reaparezca el tejido antiguo.
DETALLE_CONSERVADO = 0.6

#: Cuánto desplaza un pliegue el estampado, en fracción del ANCHO DE LA PRENDA.
#:
#: SE MIDE EN LA PRENDA, NO EN EL MOSAICO, Y ESO COSTÓ DOS VECES
#: -------------------------------------------------------------
#: Estuvo en fracciones del mosaico. Primero en 0,10, medido con mosaicos
#: procedurales suaves; al pasar a mosaicos fotográficos, un cuadro nítido se
#: derretía en cintas y hubo que bajarlo a 0,03. Y aun así, un floral grande
#: —dos mosaicos a lo ancho— salía ondulado en bandas: con el mosaico enorme, el
#: mismo 0,03 eran ±63 px, cuando en el vichy eran ±16.
#:
#: El error era de modelo, no de número: un pliegue desplaza la tela según su
#: profundidad EN LA PRENDA, no según lo grande que sea el dibujo. Ahora se mide
#: sobre el ancho de la prenda, calibrado para que el vichy sobre la camiseta
#: —donde se midió: a 0,05 ondulaba, a 0,03 seguía el hombro conservando el
#: cuadro— quede exactamente igual (0,03 × 182 px / 1435 px ≈ 0,0038).
DOBLADO_DEL_ESTAMPADO = 0.0038

#: Brillo de referencia mínimo. Una prenda negra sobre fondo negro tiene un
#: brillo medio cercano a cero, y dividir por él manda la razón al infinito.
BRILLO_MINIMO = 0.012


@dataclass(frozen=True)
class Retexturizado:
    imagen: Image.Image
    #: Cuánto relieve tenía la prenda original (desviación de la razón de luz).
    #:
    #: Por debajo de ~0,04 la prenda no tenía sombras que reutilizar —un boceto,
    #: o una foto plana— y el resultado sale como un recorte de papel pintado.
    #: Se expone para poder avisar en vez de entregar algo soso sin explicación.
    contraste: float


def retexturizar(
    prenda: Image.Image,
    mascara: Image.Image,
    tela: Image.Image,
    *,
    repeticiones: int = 6,
    caja: tuple[int, int, int, int] | None = None,
    acabado: str = "mate",
) -> Retexturizado:
    """Devuelve la prenda vestida con la tela.

    `repeticiones` es cuántas veces se repite el mosaico a lo ancho de la
    prenda: la escala del estampado. `acabado` es el de la tela NUEVA —"mate" o
    "satinado"— y decide cuánto brillo se le permite: una tela mate no hereda
    el brillo del cuero original.

    LA CAPA DE SOMBREADO, COMO LA EXTRAEN LOS CONFIGURADORES DE TELA
    ---------------------------------------------------------------
    La primera versión dividía el brillo entre su mediana y recortaba. En el
    banco de ocho prendas eso fallaba de cuatro maneras, y cada paso de aquí
    abajo arregla una:

    1. **El halo del borde.** En el canto, el píxel es mitad prenda y mitad
       fondo; con el fondo claro mezclado, la razón de luz se disparaba y
       pintaba un aro brillante fuera de la prenda. Ahora la luz se calcula
       SOLO con píxeles de prenda pura y el borde se rellena desde dentro
       (convolución normalizada).
    2. **Contraste de pliegues fuera de rango.** Medido en logaritmo: la
       camiseta blanca, 0,13 —aplastada por la sobreexposición—; la cazadora de
       cuero, 0,92 —hinchada, porque cada variación sobre un casi-negro es una
       razón enorme—. Las prendas de tono medio, que la cámara captura bien,
       dan 0,47–0,49. Se normaliza hacia ese rango.
    3. **La textura del material viejo.** La trama del vaquero o el grano del
       cuero aparecían a través de la tela nueva. Son detalle denso y fino; una
       costura es escasa y fuerte. Se mide el nivel de ese detalle fino en la
       propia prenda y se umbraliza por él: la trama se va, la costura queda.
    4. **Los brillos del material viejo.** El 35% de la cazadora está por
       encima de 1,5 veces su mediana: es el brillo del cuero, no la forma de la
       prenda. A una tela mate se le limitan las luces.
    """
    prenda = prenda.convert("RGB")
    if mascara.size != prenda.size:
        mascara = mascara.resize(prenda.size, Image.Resampling.BILINEAR)

    alfa = np.asarray(mascara.convert("L"), dtype=np.float32)[..., None] / 255.0
    ocho_bits = np.asarray(prenda)
    original = ocho_bits.astype(np.float32) / 255.0

    dentro = alfa[..., 0] > 0.5
    if not dentro.any():
        # Sin máscara no hay dónde poner la tela. Devolver la prenda tal cual
        # es más honesto que pintarla entera.
        return Retexturizado(imagen=prenda, contraste=0.0)

    lineal = _a_luz_lineal_8(ocho_bits)
    brillo = lineal @ LUMINANCIA

    # 1. SOPORTE: solo la prenda pura. Donde la máscara no llega a 0,9 el píxel
    #    mezcla prenda y fondo, y su brillo no dice nada de la luz de la prenda.
    soporte = np.clip((alfa[..., 0] - 0.9) / 0.1, 0.0, 1.0)
    if soporte.sum() < 64:
        soporte = dentro.astype(np.float32)
    puro = soporte > 0.99

    # El color propio de la prenda: la mediana de su brillo. La mediana y no la
    # media, porque un brillo especular arrastra la media y no la mediana.
    referencia = max(float(np.median(brillo[puro])), BRILLO_MINIMO)
    registro = np.log(np.maximum(brillo, referencia * 0.02) / referencia)

    ancho = prenda.width
    forma = _dentro(registro, soporte, max(1.0, ancho / 220.0))
    fino = registro - _dentro(registro, soporte, 1.0)
    textura = 1.4826 * float(np.median(np.abs(fino[puro])))

    # 3. DETALLE sin la textura del material viejo: umbral blando en unidades
    #    del propio nivel de textura. Fuera del soporte vale cero, así que el
    #    borde no mete detalle del fondo.
    detalle = (registro - forma) * soporte
    detalle = np.sign(detalle) * np.maximum(np.abs(detalle) - UMBRAL_DE_TEXTURA * textura, 0.0)

    # 2. CONTRASTE DE PLIEGUES, hacia el rango de una tela bien fotografiada.
    forma = forma - float(np.median(forma[puro]))
    q1, q3 = np.percentile(forma[puro], [25, 75])
    dispersion = float(q3 - q1) / 1.349
    forma = forma * _ganancia_de_forma(dispersion)

    luz = forma + DETALLE_CONSERVADO * detalle
    if acabado == "satinado":
        # Una seda o un raso brillan donde da la luz: las crestas de los
        # pliegues ganan algo más de lo que tenían.
        luz = luz + BRILLO_SATINADO * np.maximum(forma, 0.0)

    # 4. LUCES según la tela nueva. Techo suave (tangente hiperbólica): acerca
    #    los brillos al límite sin cortarlos en seco, que dejaría manchas planas.
    techo = float(np.log(LUZ_SATINADA if acabado == "satinado" else LUZ_MATE))
    luz = np.where(luz > 0.0, techo * np.tanh(luz / techo), luz)
    luz = np.maximum(luz, float(np.log(SOMBRA_MINIMA)))
    razon = np.exp(luz).astype(np.float32)

    # El estampado se dobla con la FORMA suave, no con el detalle: una costura
    # no debe torcer un cuadro.
    pendiente = _pendiente_de_la_prenda(np.exp(forma).astype(np.float32))
    # Cada pieza con su veta: la raya corre a lo largo de la manga.
    x, y, _ = coordenadas_de_la_veta(alfa[..., 0])
    campo = _tender_la_tela(tela, prenda.size, repeticiones, caja, pendiente, (x, y))

    vestida = _a_srgb(_a_luz_lineal(campo) * razon[..., None])
    compuesta = vestida * alfa + original * (1.0 - alfa)

    imagen = Image.fromarray(np.clip(compuesta * 255.0, 0, 255).astype(np.uint8), mode="RGB")
    return Retexturizado(imagen=imagen, contraste=dispersion)


def _dentro(campo: np.ndarray, peso: np.ndarray, radio: float) -> np.ndarray:
    """Desenfoque que solo mira dentro de la prenda (convolución normalizada).

    Se desenfoca el campo multiplicado por el peso y se divide por el peso
    desenfocado: cada píxel es la media de sus vecinos QUE SON PRENDA. En el
    borde y fuera, el valor sale de dentro — que es justo lo que quita el halo.
    """
    numerador = _desenfocar(campo * peso, radio)
    denominador = _desenfocar(peso, radio)
    lejos = denominador < 1e-4
    resultado = numerador / np.maximum(denominador, 1e-4)
    if lejos.any():
        # Muy lejos de la prenda no llega ningún vecino: se rellena con la
        # mediana, que es neutra (razón 1).
        resultado[lejos] = 0.0
    return resultado


def _ganancia_de_forma(dispersion: float) -> float:
    """Cuánto hay que estirar o encoger los pliegues para que parezcan de tela."""
    if dispersion < FORMA_MINIMA:
        return min(FORMA_MINIMA / max(dispersion, 1e-3), GANANCIA_MAXIMA_DE_FORMA)
    if dispersion > FORMA_MAXIMA:
        return FORMA_MAXIMA / dispersion
    return 1.0


#: Cuánto más oscuro queda el borde de un boceto respecto a su centro.
#:
#: Es volumen INVENTADO, y solo se usa cuando el dibujo no trae sombreado
#: propio: un plano técnico, un contorno a boli. Es poco a propósito, porque
#: inventar con énfasis es mentir con énfasis.
VOLUMEN_DEL_BOCETO = 0.38

#: Grosor máximo de un trazo, como divisor del ancho de la imagen.
#:
#: Es el radio del máximo local que borra las líneas para dejar ver el
#: sombreado que hay debajo. Demasiado pequeño y las líneas gruesas sobreviven
#: y se cuentan como sombra; demasiado grande y se come el sombreado fino.
GROSOR_DEL_TRAZO = 260.0

#: Cuánto tiene que hundirse un píxel respecto al papel de al lado para empezar
#: a contar como trazo, y para contar como trazo entero.
#:
#: Son DOS números y no uno, y ese es el punto. Medido sobre un croquis real: la
#: mitad de los píxeles de la prenda están un 11% por debajo de su entorno y el
#: 5% está por encima del 73%. Lo primero es el rayado del lápiz —el tono con el
#: que se sombrea— y lo segundo son las líneas de verdad.
#:
#: Con un solo umbral, un tercio de la prenda se conservaba como «tinta» y el
#: dibujo entero seguía viéndose en gris por encima de la tela. Con un suelo,
#: el rayado pasa a ser sombra (que es lo que es) y solo la línea se conserva.
PISO_DEL_TRAZO = 0.35
PLENO_DEL_TRAZO = 0.75

#: Anchura del desenfoque del sombreado, como divisor del ancho de la imagen.
#: Tiene que borrar el grano del papel y conservar el pliegue, que es mucho más
#: ancho. Con el croquis de referencia, un pliegue mide unos 30 px de 794.
RADIO_DEL_SOMBREADO = 110.0

#: Qué percentil del sombreado es «aquí da la luz de lleno».
#:
#: En una fotografía se usa la MEDIANA, porque una prenda real tiene luces y
#: sombras repartidas alrededor de su color propio. En un dibujo no: el papel
#: es el blanco de partida y el lápiz solo puede restar. Con la mediana, media
#: prenda saldría por encima de la tela, más clara que la tela misma.
PERCENTIL_DEL_PAPEL = 88.0

#: Relieve dibujado por debajo del cual no hay sombreado que reutilizar, y por
#: encima del cual se usa entero. Entre medias se mezcla con el inventado, para
#: que un dibujo a medio sombrear no dé un salto brusco.
RELIEVE_NULO = 0.020
RELIEVE_PLENO = 0.075


def vestir_boceto(
    boceto: Image.Image,
    mascara: Image.Image,
    tela: Image.Image,
    *,
    repeticiones: int = 6,
    caja: tuple[int, int, int, int] | None = None,
) -> Retexturizado:
    """Rellena un boceto con una tela, conservando el trazo del dibujo.

    POR QUÉ EXISTE ESTO Y NO SE MANDA TODO A LA IA
    ----------------------------------------------
    Se probó la IA con un boceto real —camisa con cartera de botones, bolsillo
    de pecho y cuello camisero— y devolvió una túnica lisa de cuello barco. Con
    el modelo mini y con el completo, y con `input_fidelity="high"`, que es el
    parámetro que existe justo para evitarlo. El modelo no conserva el diseño:
    lo reinterpreta.

    Para un producto cuya promesa es «mira TU diseño con otra tela», eso es
    exactamente el resultado equivocado. Una modista que dibuja cinco botones
    quiere ver cinco botones.

    Así que aquí el dibujo manda, entero: su trazo y su sombreado.

    EL SOMBREADO DEL DIBUJO ES LUZ, Y ANTES SE TIRABA
    -------------------------------------------------
    La primera versión rellenaba el interior con tela plana y oscurecía los
    bordes con un degradado. El usuario lo describió en una frase: «parece que
    le echara pintura a la prenda». Era exactamente eso, y el fallo estaba en
    una suposición escrita aquí mismo: que un boceto no tiene sombras.

    Un figurín SÍ las tiene. El diseñador sombrea a lápiz por dónde cae el
    pliegue, cómo se quiebra la cola, qué lado queda de espaldas a la luz. Es
    la misma información que trae una fotografía, puesta a mano — y el motor la
    estaba descartando para inventarse una peor.

    Ahora el dibujo se parte en sus dos capas (`_separar_trazo_de_sombreado`):
    el sombreado va DEBAJO multiplicando la tela, como la razón de luz de una
    foto, y el trazo va ENCIMA intacto, que es lo que mantiene el diseño.

    CUANDO EL DIBUJO NO TRAE SOMBREADO
    ----------------------------------
    Un plano técnico o un contorno a bolígrafo no tienen tonos. Ahí se vuelve
    al volumen inventado por distancia al borde, que es pobre pero honesto. La
    mezcla entre uno y otro la decide el relieve medido, no un ajuste a mano.
    """
    boceto = boceto.convert("RGB")
    if mascara.size != boceto.size:
        mascara = mascara.resize(boceto.size, Image.Resampling.BILINEAR)

    alfa = np.asarray(mascara.convert("L"), dtype=np.float32) / 255.0
    original = np.asarray(boceto, dtype=np.float32) / 255.0

    dentro = alfa > 0.5
    if not dentro.any():
        return Retexturizado(imagen=boceto, contraste=0.0)

    trazo, sombreado = _separar_trazo_de_sombreado(original, boceto.width)

    # El sombreado, convertido en luz. Mismo cociente que en una fotografía: se
    # divide entre «lo que está plenamente iluminado» y lo que queda ya no
    # depende de con qué dureza dibujara esta persona.
    referencia = max(float(np.percentile(sombreado[dentro], PERCENTIL_DEL_PAPEL)), BRILLO_MINIMO)
    dibujado = np.clip(sombreado / referencia, SOMBRA_MINIMA, 1.0)
    relieve = float(dibujado[dentro].std())

    # Volumen inventado, para los dibujos que no traen tono: lejos del borde,
    # más luz.
    hinchado = _desenfocar(alfa, max(8.0, boceto.width / 26.0))
    inventado = 1.0 - VOLUMEN_DEL_BOCETO * (1.0 - np.clip(hinchado, 0.0, 1.0))

    mezcla = float(
        np.clip((relieve - RELIEVE_NULO) / (RELIEVE_PLENO - RELIEVE_NULO), 0.0, 1.0)
    )
    modelado = mezcla * dibujado + (1.0 - mezcla) * inventado

    # Con relieve de verdad, el estampado ya puede doblarse por donde el dibujo
    # dice que se dobla. Antes no tenía sentido: la única pendiente era la del
    # degradado del borde, y curvaba los cuadros hacia fuera en todas partes.
    pendiente = _pendiente_de_la_prenda(modelado)
    campo = _tender_la_tela(tela, boceto.size, repeticiones, caja, pendiente)
    vestida = _a_srgb(_a_luz_lineal(campo) * modelado[..., None])

    # EL TRAZO SE CONSERVA, Y ES LO QUE HACE QUE SIGA SIENDO SU DISEÑO.
    tinta = trazo * alfa
    resultado = vestida * (1.0 - tinta[..., None]) + original * tinta[..., None]
    compuesta = resultado * alfa[..., None] + original * (1.0 - alfa[..., None])

    imagen = Image.fromarray(np.clip(compuesta * 255.0, 0, 255).astype(np.uint8), mode="RGB")
    return Retexturizado(imagen=imagen, contraste=relieve)


def _separar_trazo_de_sombreado(
    original: np.ndarray, ancho: int
) -> tuple[np.ndarray, np.ndarray]:
    """Parte un dibujo en sus dos capas, que son cosas distintas.

    El TRAZO define el diseño: el escote, la costura, el canto de la cola. Es
    estrecho y hay que dejarlo intacto por encima de la tela.

    El SOMBREADO es luz: ancho, suave, y dice dónde se pliega. Va debajo,
    multiplicando la tela.

    CÓMO SE SEPARAN, Y POR QUÉ NO POR OSCURIDAD
    -------------------------------------------
    La versión anterior las separaba por oscuridad absoluta: «más oscuro que
    0,62 es trazo». Eso mete en el mismo saco una línea de contorno y una
    sombra bien cargada, y como el trazo se conserva tal cual, TODA la sombra
    se quedaba dibujada en gris lápiz por encima de la tela nueva.

    Se separan por ANCHURA, que es lo que de verdad las distingue. Un máximo
    local un poco más ancho que la línea la borra —es estrecha y oscura— y deja
    el sombreado, que es ancho. Lo que la línea haya restado a esa superficie
    limpia es la línea.

    Y se mide en proporción, no en diferencia: una línea trazada sobre una zona
    ya sombreada resta menos en valor absoluto, pero es igual de línea.

    EL RAYADO NO ES LÍNEA, ES TONO
    ------------------------------
    Un croquis se sombrea rayando, y una raya de sombreado también es estrecha
    y oscura. Si se contara como trazo, se conservaría tal cual y el dibujo
    entero se vería en gris lápiz por encima de la tela nueva — que es el
    defecto que se venía a arreglar.

    Los separa la PROFUNDIDAD, y está medida: en el croquis de referencia el
    rayado hunde un 11% y el contorno un 73%. De ahí el suelo.

    Y lo que se quita para calcular el sombreado son SOLO las líneas de verdad.
    Borrar también el rayado dejaría el papel liso y se perdería justo el tono
    que el dibujante puso rayando.
    """
    lineal = _a_luz_lineal(original)
    brillo = lineal @ LUMINANCIA

    radio = max(1, round(ancho / GROSOR_DEL_TRAZO))
    sin_trazo = maximo_local(brillo, radio)

    hundido = 1.0 - brillo / np.maximum(sin_trazo, BRILLO_MINIMO)
    trazo = np.clip(
        (hundido - PISO_DEL_TRAZO) / (PLENO_DEL_TRAZO - PISO_DEL_TRAZO), 0.0, 1.0
    )

    # Donde hay línea se pone el papel de al lado; donde hay rayado se deja el
    # dibujo. Después se desenfoca: lo que queda es tono sin contornos.
    limpio = brillo * (1.0 - trazo) + sin_trazo * trazo
    sombreado = _desenfocar(limpio, max(2.0, ancho / RADIO_DEL_SOMBREADO))

    return trazo, sombreado


#: Lado al que se reduce la imagen para calcular el modelado.
LADO_DEL_MODELADO = 256


def _pendiente_de_la_prenda(razon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Hacia dónde se inclina la superficie, en cada punto.

    Devuelve el gradiente del modelado: dos campos que dicen cuánto y hacia
    dónde se curva la prenda. Es lo que dobla el estampado.

    SE DERIVA EN PEQUEÑO, Y ESE ORDEN ES TODO
    -----------------------------------------
    El primer intento reducía la imagen, desenfocaba, la AMPLIABA de vuelta y
    derivaba el resultado. Salía destrozado: la ampliación pasaba por enteros
    de 8 bits y dejaba escalones de 1/120, invisibles a la vista pero enormes
    para una derivada. El estampado se rompía en tiras verticales.

    Derivando ANTES de ampliar, se deriva un campo que sí es suave, y lo que se
    amplía es ya el resultado. Un gradiente de un campo de frecuencia muy baja
    también es de frecuencia muy baja, así que ampliarlo no inventa nada.

    Y de paso sale gratis: el desenfoque ancho, que es la parte cara, se hace
    sobre una imagen dieciséis veces más pequeña.
    """
    alto, ancho = razon.shape
    escala = min(1.0, LADO_DEL_MODELADO / max(ancho, alto))

    pequeno = reescalar(razon, max(8, round(ancho * escala)), max(8, round(alto * escala)))
    suave = _desenfocar(pequeno, max(4.0, pequeno.shape[1] / 22.0))

    gy, gx = np.gradient(suave)

    # Normalizado por su propia dispersión, para que el efecto sea el mismo en
    # una foto de estudio muy contrastada y en una plana, en vez de depender de
    # lo dura que fuera la luz. Se hace aquí, sobre el campo pequeño, donde la
    # dispersión es la de la forma y no la del ruido.
    gy = np.clip(gy / (float(gy.std()) or 1.0), -3.0, 3.0)
    gx = np.clip(gx / (float(gx.std()) or 1.0), -3.0, 3.0)

    return reescalar(gx, ancho, alto), reescalar(gy, ancho, alto)


def _tender_la_tela(
    tela: Image.Image,
    tamano: tuple[int, int],
    repeticiones: int,
    caja: tuple[int, int, int, int] | None,
    pendiente: tuple[np.ndarray, np.ndarray] | None = None,
    coordenadas: tuple[np.ndarray, np.ndarray] | None = None,
) -> np.ndarray:
    """Repite el mosaico de tela hasta cubrir la imagen, doblándolo con la prenda.

    `coordenadas` son las de textura de cada píxel, si no son las de la imagen:
    las que da `veta.coordenadas_de_la_veta`, para que una raya corra a lo largo
    de la manga y no en vertical por toda la foto.

    LA ESCALA SE MIDE SOBRE LA PRENDA, NO SOBRE LA IMAGEN
    -----------------------------------------------------
    Si se usara el ancho de la imagen, la misma tela cambiaría de tamaño según
    el margen que tuviera la foto alrededor, y dos pruebas de la misma prenda
    dejarían de ser comparables — que es justo lo que el producto promete.

    SE REPITE SIN ESPEJAR
    ---------------------
    Espejando no se notarían las uniones del mosaico, pero una raya se
    convertiría en un galón en cada una. En confección la dirección del hilo es
    un dato real, no un detalle estético.

    EL ESTAMPADO SE DOBLA CON LOS PLIEGUES
    --------------------------------------
    Repetir el dibujo en plano delata el montaje en cuanto la tela tiene
    estampado: los cuadros salen perfectamente rectos sobre una manga arrugada,
    como papel pintado sobre una escultura.

    La pista de por dónde se dobla ya la tenemos, y gratis: el mapa de luz. Su
    gradiente apunta hacia donde la superficie se inclina, así que desplazando
    las coordenadas de la textura en esa dirección —y en proporción a la
    pendiente— el dibujo se curva siguiendo el relieve.

    No es una reconstrucción de la forma en 3D: deducir el volumen exacto a
    partir de sombras es un problema sin solución única. Es una aproximación
    que acierta en lo que se ve, y cuesta un gradiente.
    """
    ancho_prenda = (caja[2] - caja[0]) if caja else tamano[0]
    ancho_prenda = max(ancho_prenda, 8)

    lado = max(8, round(ancho_prenda / max(1, repeticiones)))
    mosaico = np.asarray(
        tela.convert("RGB").resize((lado, lado), Image.Resampling.LANCZOS), dtype=np.float32
    ) / 255.0

    if coordenadas is not None:
        x, y = coordenadas[0].copy(), coordenadas[1].copy()
    else:
        columnas = np.arange(tamano[0], dtype=np.float32)[None, :]
        filas = np.arange(tamano[1], dtype=np.float32)[:, None]
        x = np.broadcast_to(columnas, (tamano[1], tamano[0])).copy()
        y = np.broadcast_to(filas, (tamano[1], tamano[0])).copy()

    if pendiente is not None:
        gx, gy = pendiente
        empuje = ancho_prenda * DOBLADO_DEL_ESTAMPADO
        x += gx * empuje
        y += gy * empuje

    # MUESTREO BILINEAL, Y NO ES UN LUJO
    # ----------------------------------
    # El desplazamiento del pliegue es fraccionario: medio píxel aquí, un tercio
    # allá. Truncándolo a entero —que es lo que hacía— la tela no se curva: se
    # escalona, y en un cuadro escocés los escalones se ven como dientes.
    #
    # El módulo va sobre los ÍNDICES y no sobre las coordenadas, así que la
    # interpolación cruza la costura del mosaico sin partirse: el píxel que
    # sigue al último es el primero, que es exactamente lo que significa que un
    # mosaico sea repetible.
    #
    # Se hace con `remap` de OpenCV y borde en envoltura, que es exactamente
    # esa interpolación bilineal cruzando la costura del mosaico, en C: la
    # versión con índices de numpy eran 2,2 s de una prueba de 3 megapíxeles.
    # Las coordenadas se reducen antes al mosaico para que no se pierda
    # precisión con valores grandes.
    import cv2

    x = np.mod(x, lado).astype(np.float32)
    y = np.mod(y, lado).astype(np.float32)
    return cv2.remap(
        np.ascontiguousarray(mosaico, dtype=np.float32), x, y,
        interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP,
    )


# --- Conversión de color ----------------------------------------------------
#
# Las dos mitades de la curva sRGB. El tramo recto cerca del negro no es un
# capricho de la norma: evita que la derivada se dispare en cero, que es lo que
# haría una potencia pura.


#: La curva sRGB, tabulada. Las imágenes llegan en 8 bits, así que pasar a luz
#: lineal es consultar una tabla de 256 valores en vez de elevar a 2,4 cada
#: píxel. Y la vuelta a sRGB se hace con una tabla fina de 16 384 valores: el
#: resultado se guarda en 8 bits de todas formas, y con este paso el error
#: queda por debajo de medio nivel. Las dos potencias eran 1,8 s de una prueba.
_TABLA_LINEAL = np.where(
    np.arange(256) / 255.0 <= 0.04045,
    (np.arange(256) / 255.0) / 12.92,
    ((np.arange(256) / 255.0 + 0.055) / 1.055) ** 2.4,
).astype(np.float32)
_PASOS_SRGB = 16384
_TABLA_SRGB = (lambda c: np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055))(
    np.linspace(0.0, 1.0, _PASOS_SRGB)
).astype(np.float32)


def _a_luz_lineal_8(imagen: np.ndarray) -> np.ndarray:
    """De 8 bits a luz lineal por tabla. `imagen` es uint8."""
    return _TABLA_LINEAL[imagen]


def _a_luz_lineal(c: np.ndarray) -> np.ndarray:
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _a_srgb(c: np.ndarray) -> np.ndarray:
    indice = np.clip(c, 0.0, 1.0) * (_PASOS_SRGB - 1)
    return _TABLA_SRGB[(indice + 0.5).astype(np.int32)]


def _a_srgb_exacto(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)
