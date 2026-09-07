"""Generador de diseños simulado. **No es inteligencia artificial.**

QUÉ HACE
--------
Dibuja una silueta de prenda con Pillow, eligiendo forma y color a partir de
las PALABRAS del texto: si escribes "vestido largo rojo", sale una silueta de
vestido en rojo. No entiende la frase; busca términos conocidos en una lista
corta y deliberadamente tonta.

POR QUÉ EXISTE
--------------
Para que la Fase 2 completa —escribir, generar, ver, iterar y probarse el
diseño— funcione y se pueda usar sin cuenta de pago ni conexión. Cuando
llegue el proveedor real, se escribe su clase y solo cambia lo que devuelve
`get_design_provider()`.

DETERMINISTA A PROPÓSITO
------------------------
El mismo texto produce siempre la misma imagen, porque la semilla sale de un
hash del texto. Así los tests pueden afirmar cosas concretas, y al iterar se
nota que el resultado cambia porque cambió la instrucción, no por azar.
"""

import hashlib
import io

from PIL import Image, ImageDraw

from app.ai.design_provider import DesignProviderError

SHAPES = {
    "vestido": "dress", "dress": "dress", "falda": "dress",
    "pantalon": "bottom", "pantalón": "bottom", "vaquero": "bottom",
    "jeans": "bottom", "short": "bottom",
    "abrigo": "outer", "chaqueta": "outer", "coat": "outer", "jacket": "outer",
}

COLORS = {
    "rojo": "#dc2626", "red": "#dc2626",
    "azul": "#2563eb", "blue": "#2563eb",
    "verde": "#16a34a", "green": "#16a34a",
    "negro": "#171717", "black": "#171717",
    "blanco": "#f5f5f5", "white": "#f5f5f5",
    "amarillo": "#eab308", "yellow": "#eab308",
    "rosa": "#ec4899", "pink": "#ec4899",
    "morado": "#7c3aed", "violeta": "#7c3aed", "purple": "#7c3aed",
    "gris": "#6b7280", "gray": "#6b7280", "beige": "#d6c7b0",
}

# Paleta de reserva cuando el texto no menciona ningún color conocido.
FALLBACK_COLORS = ["#8b5cf6", "#0ea5e9", "#f59e0b", "#10b981", "#ef4444", "#64748b"]

CANVAS = (640, 800)


class MockDesignProvider:
    """Generador simulado con Pillow. Cumple `DesignProvider`."""

    name = "mock-design"

    def generate(
        self,
        *,
        prompt: str,
        base_image: bytes | None = None,
        refinement: str | None = None,
    ) -> bytes:
        if not prompt.strip():
            raise DesignProviderError("La descripción está vacía.")

        # Al iterar, el texto de la instrucción se suma al original, así que
        # forma y color pueden cambiar respecto al diseño padre. Es justo lo
        # que se espera de una iteración.
        texto = f"{prompt} {refinement or ''}".lower()

        try:
            return self._draw(texto, iterando=base_image is not None)
        except Exception as exc:  # noqa: BLE001
            raise DesignProviderError("No se pudo generar el diseño.") from exc

    # --- Interno ---

    def _semilla(self, texto: str) -> int:
        return int(hashlib.sha256(texto.encode("utf-8")).hexdigest()[:8], 16)

    def _color(self, texto: str) -> str:
        for palabra, color in COLORS.items():
            if palabra in texto:
                return color
        return FALLBACK_COLORS[self._semilla(texto) % len(FALLBACK_COLORS)]

    def _forma(self, texto: str) -> str:
        for palabra, forma in SHAPES.items():
            if palabra in texto:
                return forma
        return "top"

    def _draw(self, texto: str, *, iterando: bool) -> bytes:
        color = self._color(texto)
        forma = self._forma(texto)

        # Fondo transparente: así el diseño se puede componer sobre una foto
        # en el probador sin arrastrar un rectángulo de fondo.
        image = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        ancho, alto = CANVAS

        if forma == "dress":
            draw.polygon([(240, 110), (400, 110), (430, 330), (530, 760),
                          (110, 760), (210, 330)], fill=color)
            draw.polygon([(240, 110), (185, 250), (230, 265)], fill=color)
            draw.polygon([(400, 110), (455, 250), (410, 265)], fill=color)
        elif forma == "bottom":
            draw.polygon([(190, 120), (450, 120), (435, 760), (340, 760),
                          (320, 400), (300, 760), (205, 760)], fill=color)
        elif forma == "outer":
            draw.polygon([(215, 120), (425, 120), (430, 640), (210, 640)], fill=color)
            draw.polygon([(215, 120), (135, 330), (200, 350), (215, 210)], fill=color)
            draw.polygon([(425, 120), (505, 330), (440, 350), (425, 210)], fill=color)
            # Solapa: distingue un abrigo de una camiseta de un vistazo.
            draw.polygon([(320, 120), (270, 250), (320, 300), (370, 250)],
                         fill=(255, 255, 255, 60))
        else:  # top
            draw.polygon([(220, 130), (420, 130), (425, 610), (215, 610)], fill=color)
            draw.polygon([(220, 130), (140, 330), (205, 350), (220, 240)], fill=color)
            draw.polygon([(420, 130), (500, 330), (435, 350), (420, 240)], fill=color)
            draw.ellipse([(280, 110), (360, 170)], fill=(0, 0, 0, 0))

        # Franja inferior que marca visualmente que esto es una iteración.
        # Sin ella, dos diseños de la misma cadena podrían parecer idénticos y
        # daría la impresión de que el botón de iterar no hace nada.
        if iterando:
            draw.rectangle([(0, alto - 14), (ancho, alto)], fill=color)

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
