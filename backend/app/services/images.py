"""Validación de imágenes subidas.

Hasta la Fase 1, el tipo de un archivo se decidía leyendo la cabecera
`Content-Type` que envía el cliente. Esa cabecera la escribe quien sube el
archivo, así que no prueba nada: basta con declarar `image/png` para colar
cualquier cosa (limitación #6 de PROJECT_STATUS.md).

Aquí se comprueba el contenido de verdad: se abre el archivo con Pillow y se
usa el formato que Pillow detecta, no el que dice el cliente. Un ejecutable
renombrado a `.png` no pasa.

Importa ahora más que antes porque en la Fase 1 se aceptan **fotografías de
personas**, no solo imágenes de catálogo que sube el propio administrador.
"""

import io

from PIL import Image, UnidentifiedImageError

from app.services.exceptions import ValidationError

# Formatos que Pillow detecta y que aceptamos, con la extensión que les
# corresponde. La clave es el nombre de formato de Pillow (`Image.format`).
ALLOWED_FORMATS: dict[str, str] = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}

# Tope de dimensiones. Una imagen de 30.000 x 30.000 píxeles ocupa poco
# comprimida pero revienta la memoria al descomprimirla: es la "bomba de
# descompresión". Pillow avisa por encima de ~89 millones de píxeles; aquí se
# corta antes y con un mensaje que el usuario entiende.
MAX_PIXELS = 50_000_000


def validate_image(content: bytes, *, max_bytes: int) -> str:
    """Comprueba que `content` es una imagen aceptable y devuelve su extensión.

    Lanza `ValidationError` con un mensaje presentable si no lo es.
    """
    if not content:
        raise ValidationError("El archivo está vacío.")

    if len(content) > max_bytes:
        raise ValidationError(
            f"La imagen supera el tamaño máximo de {max_bytes // (1024 * 1024)} MB."
        )

    try:
        with Image.open(io.BytesIO(content)) as image:
            image_format = image.format
            width, height = image.size
            # `verify()` detecta archivos truncados o corruptos. Deja la imagen
            # inutilizable, por eso se lee todo lo que hace falta ANTES.
            image.verify()
    except UnidentifiedImageError as exc:
        raise ValidationError(
            "El archivo no es una imagen válida. Se aceptan JPEG, PNG y WebP."
        ) from exc
    except Exception as exc:  # noqa: BLE001 - Pillow lanza tipos muy variados
        raise ValidationError("La imagen está dañada o incompleta.") from exc

    extension = ALLOWED_FORMATS.get(image_format or "")
    if extension is None:
        aceptados = ", ".join(sorted(ALLOWED_FORMATS))
        raise ValidationError(
            f"Formato de imagen no admitido ({image_format or 'desconocido'}). "
            f"Se aceptan: {aceptados}."
        )

    if width * height > MAX_PIXELS:
        raise ValidationError(
            f"La imagen es demasiado grande ({width}x{height} píxeles). "
            "Redúcela antes de subirla."
        )

    return extension
