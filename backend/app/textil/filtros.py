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
    """Media móvil en un eje, en coma flotante, con el borde replicado.

    PRIMERO FUE CON SUMAS ACUMULADAS, Y ERA EL 60% DEL TIEMPO
    --------------------------------------------------------
    La primera versión usaba sumas acumuladas en doble precisión: coste
    constante por píxel y sin pérdida de dígitos, que importa porque de este
    campo se calculan después gradientes. En una foto de 3 megapíxeles eso eran
    8 de los 13 segundos de una prueba.

    Ahora es el filtro de caja de OpenCV, en C, sobre coma flotante de 32 bits.
    Se midió antes de cambiarlo: entre 15 y 35 veces más rápido, error máximo
    de 1e-7 frente a la versión en doble precisión, y en el gradiente también de
    1e-7 frente a un gradiente típico de 5e-3. La precisión que protegía la
    regla de «no cuantizar lo que se va a derivar» se conserva.
    """
    import cv2

    if radio < 1:
        return campo
    lado = 2 * radio + 1
    tamano = (lado, 1) if eje == 1 else (1, lado)
    return cv2.boxFilter(
        np.ascontiguousarray(campo, dtype=np.float32), -1, tamano,
        normalize=True, borderType=cv2.BORDER_REPLICATE,
    )


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
