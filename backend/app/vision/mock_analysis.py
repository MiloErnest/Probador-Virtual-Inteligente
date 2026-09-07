"""Analizador corporal simulado. **No es visión por computador.**

QUÉ HACE
--------
Mira la relación de aspecto de la fotografía y deriva las medidas de una
altura de referencia usando proporciones antropométricas medias. Nada más.
No detecta a la persona, no encuentra articulaciones, no mide el cuerpo.

POR QUÉ ESTO Y NO MEDIAPIPE YA
------------------------------
MediaPipe son cientos de megabytes de dependencias y un modelo que descargar,
y aun así no resuelve lo difícil: pasar de puntos de pose a centímetros hace
falta conocer la distancia a la cámara. Instalarlo ahora sería cargar el
proyecto con peso sin haber decidido todavía cómo se hace la conversión.

Con este simulado, todo lo que rodea al análisis —subir la foto, guardar el
perfil, recomendar talla, mostrarlo— queda construido y probado. Cuando entre
MediaPipe, cumple este mismo contrato y no cambia nada más.

DETERMINISTA
------------
La misma foto y la misma altura dan siempre las mismas medidas. Sin eso, los
tests no podrían afirmar nada y el usuario vería números distintos cada vez
que analizara la misma imagen, lo que parecería un fallo.

LA CONFIANZA QUE DECLARA ES BAJA A PROPÓSITO
--------------------------------------------
0.35 con altura conocida, 0.15 sin ella. Es honesto: estas medidas son una
estimación grosera, y la interfaz debe poder avisar de ello. Un simulado que
dijera 0.95 mentiría a quien lo lea.
"""

import hashlib
import io

from PIL import Image, ImageOps

from app.vision.analysis_provider import BodyAnalysisError, BodyMeasurements

# Altura supuesta cuando el usuario no la indica. Es una media adulta amplia;
# el error que introduce es exactamente el motivo por el que conviene pedirla.
DEFAULT_HEIGHT_CM = 170.0

# Proporciones medias sobre la altura total. Salen de tablas antropométricas
# de uso común en patronaje. Son medias: valen para dar un punto de partida,
# no para vestir a nadie a medida.
CHEST_RATIO = 0.52
WAIST_RATIO = 0.45
HIPS_RATIO = 0.54
INSEAM_RATIO = 0.46

# Cuánto se permite que la variación por foto desvíe cada medida: +-6 %.
# Suficiente para que dos fotos distintas den resultados distintos —que es lo
# que hace creíble la simulación— sin llegar a valores absurdos.
VARIATION = 0.06

# Límites de cordura de la altura. Fuera de esto, la entrada está mal.
MIN_HEIGHT_CM = 50.0
MAX_HEIGHT_CM = 260.0


class MockBodyAnalysisProvider:
    """Estimación simulada. Cumple `BodyAnalysisProvider`."""

    name = "mock-analysis"

    def analyse(self, *, photo: bytes, height_cm: float | None = None) -> BodyMeasurements:
        try:
            with Image.open(io.BytesIO(photo)) as imagen:
                imagen = ImageOps.exif_transpose(imagen)
                ancho, alto = imagen.size
        except Exception as exc:  # noqa: BLE001
            raise BodyAnalysisError(
                "No se pudo leer la fotografía. Prueba con otra imagen."
            ) from exc

        if ancho == 0 or alto == 0:
            raise BodyAnalysisError("La fotografía está vacía.")

        # Una foto apaisada casi nunca contiene a una persona de cuerpo
        # entero. Avisar es más útil que devolver medidas malas en silencio.
        if ancho > alto * 1.4:
            raise BodyAnalysisError(
                "La fotografía es apaisada. Para estimar las medidas hace falta "
                "una foto vertical, de cuerpo entero y de frente."
            )

        altura = height_cm if height_cm is not None else DEFAULT_HEIGHT_CM
        if not MIN_HEIGHT_CM <= altura <= MAX_HEIGHT_CM:
            raise BodyAnalysisError(
                f"La altura indicada ({altura:g} cm) está fuera de lo razonable."
            )

        # Desviación determinista a partir del contenido de la imagen: dos
        # fotos distintas dan medidas distintas, la misma foto siempre igual.
        semilla = int(hashlib.sha256(photo).hexdigest()[:8], 16)
        desvio = ((semilla % 2000) / 1000.0 - 1.0) * VARIATION  # de -0.06 a +0.06

        def medida(ratio: float, giro: float) -> float:
            return round(altura * ratio * (1 + desvio * giro), 1)

        return BodyMeasurements(
            height_cm=round(altura, 1),
            # Cada medida usa un múltiplo distinto del desvío para que no
            # varíen todas al unísono, que delataría el truco a simple vista.
            chest_cm=medida(CHEST_RATIO, 1.0),
            waist_cm=medida(WAIST_RATIO, 1.4),
            hips_cm=medida(HIPS_RATIO, 0.8),
            inseam_cm=medida(INSEAM_RATIO, 0.5),
            # Baja a propósito. Estas medidas son una estimación grosera y la
            # interfaz debe poder decirlo.
            confidence=0.35 if height_cm is not None else 0.15,
        )
