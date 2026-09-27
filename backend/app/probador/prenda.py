"""La prenda que se le manda al modelo, recortada del taller.

SON LOS MISMOS PÍXELES, NO UNA VERSIÓN NUEVA
--------------------------------------------
Si la prenda viene de una prueba de tela, se recorta de la imagen que ya se
generó en esa prueba, con la máscara que ya se calculó al subir la prenda. No
se vuelve a generar nada: lo que el usuario eligió en la comparación es
exactamente lo que se le pone a la persona.

Se manda sobre blanco y recortada a su caja, como una foto de producto
(«flat-lay»): es el formato con el que el modelo entiende mejor qué es la
prenda, y así no se cuela el fondo de la foto original ni, en una foto con
modelo, la persona que la llevaba puesta.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

#: Aire alrededor de la prenda, en fracción de su lado mayor.
MARGEN = 0.06


def recortar_prenda(imagen: Image.Image, mascara: Image.Image) -> Image.Image:
    """La prenda sobre blanco, recortada a su caja con un poco de margen."""
    imagen = imagen.convert("RGB")
    mascara = mascara.convert("L")
    if mascara.size != imagen.size:
        mascara = mascara.resize(imagen.size, Image.Resampling.BILINEAR)

    alfa = np.asarray(mascara, dtype=np.float32)[..., None] / 255.0
    px = np.asarray(imagen, dtype=np.float32)
    sobre_blanco = Image.fromarray((px * alfa + 255.0 * (1.0 - alfa) + 0.5).astype(np.uint8))

    caja = mascara.point(lambda v: 255 if v > 127 else 0).getbbox()
    if caja is None:
        return sobre_blanco
    x0, y0, x1, y1 = caja
    m = round(MARGEN * max(x1 - x0, y1 - y0))
    return sobre_blanco.crop(
        (max(0, x0 - m), max(0, y0 - m), min(imagen.width, x1 + m), min(imagen.height, y1 + m))
    )
