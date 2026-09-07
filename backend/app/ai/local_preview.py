"""Proveedor de vista previa local. **No es inteligencia artificial.**

QUÉ HACE Y QUÉ NO
-----------------
Superpone la imagen de la prenda sobre la foto, escalada y centrada sobre el
torso. No detecta la pose, no entiende el cuerpo, no adapta la tela ni las
sombras. El resultado es una composición, no una prueba virtual.

POR QUÉ EXISTE
--------------
Para que la tubería completa —subir foto, encolar, procesar, guardar el
resultado, mostrarlo— sea real y se pueda probar HOY, sin cuenta de pago,
sin clave de API y sin conexión.

Elegir el proveedor de IA es una decisión con coste que corresponde al
usuario. Sin esta clase, esa decisión bloquearía toda la Fase 1; con ella,
bloquea una sola clase. Cuando llegue el proveedor real, se escribe junto a
esta y solo cambia lo que devuelve `get_try_on_provider()`.

También queda como red de seguridad: si el servicio de IA se cae o se agota
la cuota, se puede volver a `AI_PROVIDER=local` y la aplicación sigue
funcionando de forma degradada en vez de romperse.

La interfaz avisa de que esto es una vista previa. No se presenta como IA.
"""

import io

from PIL import Image, ImageOps

from app.ai.provider import TryOnProviderError

# Proporción del ancho de la persona que ocupará la prenda. 0.55 deja la
# prenda claramente dentro de la silueta en una foto de medio cuerpo.
GARMENT_WIDTH_RATIO = 0.55

# Altura a la que se centra la prenda, medida desde arriba. 0.45 cae sobre el
# torso en un encuadre típico de medio cuerpo o cuerpo entero.
GARMENT_CENTER_Y_RATIO = 0.45

# Lado máximo del resultado. Evita devolver imágenes enormes que tardan en
# viajar al navegador sin aportar nada.
MAX_OUTPUT_SIDE = 1400


class LocalPreviewProvider:
    """Composición local con Pillow. Cumple `TryOnProvider`."""

    name = "local-preview"

    def generate(self, *, person: bytes, garment: bytes) -> bytes:
        try:
            person_image = self._open(person)
            garment_image = self._open(garment)
        except TryOnProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - Pillow lanza tipos variados
            raise TryOnProviderError(
                "No se pudieron leer las imágenes de entrada."
            ) from exc

        try:
            return self._compose(person_image, garment_image)
        except Exception as exc:  # noqa: BLE001
            raise TryOnProviderError(
                "No se pudo generar la vista previa a partir de estas imágenes."
            ) from exc

    # --- Interno ---

    def _open(self, data: bytes) -> Image.Image:
        image = Image.open(io.BytesIO(data))
        # `exif_transpose` respeta la orientación que graba la cámara del
        # móvil. Sin esto, las fotos verticales salen tumbadas: los píxeles
        # están girados y la rotación real vive en los metadatos EXIF.
        image = ImageOps.exif_transpose(image)
        return image.convert("RGBA")

    def _compose(self, person: Image.Image, garment: Image.Image) -> bytes:
        person = self._limit_size(person)

        target_width = max(1, int(person.width * GARMENT_WIDTH_RATIO))
        scale = target_width / garment.width
        target_height = max(1, int(garment.height * scale))
        garment = garment.resize((target_width, target_height), Image.LANCZOS)

        # Coordenadas de la esquina superior izquierda para que la prenda
        # quede centrada horizontalmente y a la altura del torso.
        left = (person.width - garment.width) // 2
        top = int(person.height * GARMENT_CENTER_Y_RATIO) - garment.height // 2

        canvas = person.copy()
        # La prenda se usa como su propia máscara: si trae transparencia
        # (PNG/WebP recortados) se respeta; si no, se pega como un rectángulo.
        canvas.alpha_composite(garment, dest=(max(0, left), max(0, top)))

        buffer = io.BytesIO()
        # PNG y no JPEG: el resultado se puede volver a componer más adelante
        # y no interesa acumular pérdida de calidad en cada paso.
        canvas.convert("RGB").save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()

    def _limit_size(self, image: Image.Image) -> Image.Image:
        if max(image.size) <= MAX_OUTPUT_SIDE:
            return image
        ratio = MAX_OUTPUT_SIDE / max(image.size)
        new_size = (max(1, int(image.width * ratio)), max(1, int(image.height * ratio)))
        return image.resize(new_size, Image.LANCZOS)
