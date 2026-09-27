"""Filtros numéricos compartidos por el motor textil.

Viven aquí y no dentro de un módulo concreto porque los usan dos: el recorte,
para decidir qué es fondo sin que el ruido mande, y el retexturizado, para
separar la forma de la prenda de la trama del tejido.

TODO EN COMA FLOTANTE, Y NO ES UN CAPRICHO
------------------------------------------
Pillow desenfoca en enteros de 0 a 255. Sobre una imagen no se nota; sobre un
campo del que después se calcula el GRADIENTE, sí: derivar amplifica el ruido
fino, y los escalones de 1/255 pasan a ser casi toda la señal. Costó un rato
descubrirlo — el estampado salía troceado en moaré en lugar de doblarse con los
pliegues, y la causa estaba a dos funciones de distancia del síntoma.
"""

from __future__ import annotations

import numpy as np


def media_en_ventana(campo: np.ndarray, radio: int, eje: int) -> np.ndarray:
    """Media móvil en un eje, en tiempo constante por píxel.

    Con sumas acumuladas, la suma de cualquier ventana es una resta de dos
    valores ya calculados. El coste no depende del radio, que es lo que permite
    usar radios de decenas de píxeles sin que el desenfoque domine el tiempo.

    El acumulado va en doble precisión: sumar mil cuatrocientos valores en coma
    flotante de 32 bits pierde dígitos justo donde después vamos a derivar.
    """
    if radio < 1:
        return campo

    ancho = 2 * radio + 1
    relleno = [(0, 0), (0, 0)]
    relleno[eje] = (radio, radio)
    extendido = np.pad(campo.astype(np.float64), relleno, mode="edge")

    acumulado = np.cumsum(extendido, axis=eje)
    forma_cero = list(acumulado.shape)
    forma_cero[eje] = 1
    acumulado = np.concatenate([np.zeros(forma_cero), acumulado], axis=eje)

    n = campo.shape[eje]
    superior = np.take(acumulado, np.arange(ancho, ancho + n), axis=eje)
    inferior = np.take(acumulado, np.arange(0, n), axis=eje)
    return ((superior - inferior) / ancho).astype(np.float32)


def reescalar(campo: np.ndarray, ancho: int, alto: int) -> np.ndarray:
    """Cambia el tamaño de un campo numérico SIN pasar por enteros.

    Pillow no sabe desenfocar en coma flotante, pero sí sabe reescalar: el modo
    "F" funciona con `resize` aunque falle con `filter`. Aprovecharlo evita el
    viaje de ida y vuelta por 8 bits, que es de donde salía el ruido que
    destrozaba el gradiente.
    """
    from PIL import Image

    if (campo.shape[1], campo.shape[0]) == (ancho, alto):
        return campo
    return np.asarray(
        Image.fromarray(campo.astype(np.float32), mode="F").resize(
            (ancho, alto), Image.Resampling.BILINEAR
        ),
        dtype=np.float32,
    )


def maximo_local(campo: np.ndarray, radio: int) -> np.ndarray:
    """Máximo en una ventana cuadrada. Borra lo fino y oscuro, deja lo ancho.

    PARA QUÉ SIRVE AQUÍ
    -------------------
    Es la forma de quitar el TRAZO de un dibujo sin tocar el SOMBREADO. Una
    línea de lápiz es estrecha y más oscura que el papel que la rodea, así que
    el máximo de una ventana un poco más ancha que la línea devuelve el papel.
    Una mancha de sombreado es más ancha que la ventana y sobrevive entera.

    Lo que la línea haya restado a esa superficie sin líneas **es** la línea, y
    esa resta es justo lo que hay que conservar por encima de la tela.

    Se hace por separado en cada eje: el máximo de un cuadrado es el máximo de
    los máximos de sus filas, así que dos pasadas de una dimensión dan lo mismo
    que una de dos, y cuestan 2·(2r+1) comparaciones en vez de (2r+1)².
    """
    if radio < 1:
        return campo
    for eje in (0, 1):
        campo = _maximo_en_eje(campo, radio, eje)
    return campo


def _maximo_en_eje(campo: np.ndarray, radio: int, eje: int) -> np.ndarray:
    relleno = [(0, 0), (0, 0)]
    relleno[eje] = (radio, radio)
    # Borde replicado: con ceros, el máximo del borde sería el del interior y
    # daría igual, pero con mínimos la silueta se comería un anillo.
    extendido = np.pad(campo, relleno, mode="edge")

    n = campo.shape[eje]
    salida = np.take(extendido, np.arange(n), axis=eje).copy()
    for desplazamiento in range(1, 2 * radio + 1):
        salida = np.maximum(
            salida, np.take(extendido, np.arange(desplazamiento, desplazamiento + n), axis=eje)
        )
    return salida


def media_de_caja(campo: np.ndarray, radio: int) -> np.ndarray:
    """Media en una ventana cuadrada de lado 2·radio+1. Coste constante por píxel."""
    return media_en_ventana(media_en_ventana(campo, radio, 0), radio, 1)


def filtro_guiado(guia: np.ndarray, entrada: np.ndarray, radio: int, eps: float) -> np.ndarray:
    """Filtro guiado (He, Sun y Tang, 2010): suaviza `entrada` respetando los bordes de `guia`.

    PARA QUÉ SE USA AQUÍ
    --------------------
    La máscara de la prenda se calcula a 512 px y hay que llevarla al tamaño de
    la foto. Ampliándola sin más, su borde queda donde caía en la imagen
    pequeña: en una foto de 2048 px eso es hasta ±8 px fuera del contorno real,
    y todo lo que cae en esa franja era tela pintada encima del fondo. Es el
    halo que rodeaba a casi todas las prendas.

    El filtro guiado modela la salida como una función LINEAL de la guía en cada
    ventana, ajustada por mínimos cuadrados a la entrada. Donde la foto tiene
    un borde, la máscara lo sigue; donde la foto es lisa, la máscara se
    suaviza. Es el método estándar para refinar máscaras y para ampliar mapas
    respetando los bordes, y todo son medias de caja: coste lineal.

    `eps` decide cuánto borde hace falta para que se respete. Pequeño: se pega a
    bordes débiles, como una camiseta blanca sobre fondo gris claro.
    """
    media_g = media_de_caja(guia, radio)
    media_e = media_de_caja(entrada, radio)
    varianza = media_de_caja(guia * guia, radio) - media_g * media_g
    covarianza = media_de_caja(guia * entrada, radio) - media_g * media_e

    a = covarianza / (varianza + eps)
    b = media_e - a * media_g
    return media_de_caja(a, radio) * guia + media_de_caja(b, radio)


def desenfocar(campo: np.ndarray, radio: float) -> np.ndarray:
    """Desenfoque suave, sin pasar por 8 bits.

    Tres pasadas de media móvil se parecen mucho a una gaussiana —es el teorema
    central del límite aplicado a un núcleo— y se pueden hacer en coma flotante
    de principio a fin.
    """
    r = max(1, round(radio * 0.6))
    for _ in range(3):
        campo = media_en_ventana(campo, r, 0)
        campo = media_en_ventana(campo, r, 1)
    return campo
