"""Qué es cada píxel de una persona: pelo, cara, brazos, ropa de arriba…

PARA QUÉ HACE FALTA
-------------------
El modelo que viste a la persona no se limita a la prenda. Medido con salidas
reales de FASHN VTON: regenera una caja entera alrededor del torso, y dentro de
ella cambia lo que le parece — en una foto frente a un espejo cambió la
ventana, un cuadro de la pared y los objetos del tocador, y añadió un
cinturón. Con la diferencia de píxeles no basta para deshacerlo: ese fondo
inventado ES distinto del original, igual que la prenda.

Lo que separa una cosa de otra es saber QUÉ es cada píxel. Con eso, de la
imagen generada se toma solo la ropa que se está probando —y la piel que la
prenda nueva destapa o tapa—, y todo lo demás vuelve a ser la foto original.

EL MODELO
---------
SegFormer B2 (Xie et al., 2021) ajustado para ropa sobre el conjunto ATR, con
18 clases: fondo, sombrero, pelo, gafas, ropa de arriba, falda, pantalón,
vestido, cinturón, zapatos, cara, piernas, brazos, bolso y bufanda. Es el
tipo de «analizador de personas» que usan los propios probadores virtuales
para decidir qué zona repintar.

- Se ejecuta en CPU con onnxruntime, en versión cuantizada de 28 MB: medido,
  0,8 s por foto en el portátil de desarrollo, sin tarjeta gráfica.
- Se descarga de Hugging Face la primera vez que hace falta y queda en la
  caché local. La revisión está fijada: el mismo código da siempre el mismo
  análisis.
- Licencia: los pesos derivan de SegFormer de NVIDIA, cuya licencia es de uso
  NO comercial. Vale para este proyecto universitario; para un producto habría
  que sustituirlo por un analizador con licencia comercial.
"""

from __future__ import annotations

import threading

import numpy as np
from PIL import Image

from app.textil.errores import ErrorDeMotor

REPOSITORIO = "Xenova/segformer_b2_clothes"
ARCHIVO = "onnx/model_quantized.onnx"
REVISION = "cb6ac44e641faa309f29561c1afe08d87ef52631"

#: Lado al que se reduce la foto para el modelo: con el que se entrenó.
LADO_DEL_MODELO = 512

# Las 18 clases del modelo (config.json del repositorio).
FONDO = 0
SOMBRERO = 1
PELO = 2
GAFAS = 3
ROPA_ARRIBA = 4
FALDA = 5
PANTALON = 6
VESTIDO = 7
CINTURON = 8
ZAPATO_IZQ = 9
ZAPATO_DER = 10
CARA = 11
PIERNA_IZQ = 12
PIERNA_DER = 13
BRAZO_IZQ = 14
BRAZO_DER = 15
BOLSO = 16
BUFANDA = 17
CLASES = 18

_MEDIA = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_DESVIACION = np.array([0.229, 0.224, 0.225], dtype=np.float32)

_sesion = None
_cerrojo = threading.Lock()


def _sesion_del_modelo():
    """La sesión de onnxruntime, cargada una vez por proceso."""
    global _sesion
    with _cerrojo:
        if _sesion is None:
            try:
                import onnxruntime as ort
                from huggingface_hub import hf_hub_download

                try:
                    # Primero la copia local, sin red: huggingface.co puede
                    # tardar minutos en responder desde una red sin IPv6 (ver
                    # VTO_SPACE en la configuración), y la revisión está fijada,
                    # así que la copia local es exactamente la que se quiere.
                    ruta = hf_hub_download(
                        REPOSITORIO, ARCHIVO, revision=REVISION, local_files_only=True
                    )
                except Exception:  # noqa: BLE001
                    ruta = hf_hub_download(REPOSITORIO, ARCHIVO, revision=REVISION)
                _sesion = ort.InferenceSession(ruta, providers=["CPUExecutionProvider"])
            except Exception as exc:  # noqa: BLE001
                raise ErrorDeMotor(
                    "No se ha podido cargar el analizador de personas "
                    f"({REPOSITORIO}). La primera vez se descarga de Hugging Face "
                    "(28 MB): comprueba la conexión y vuelve a intentarlo."
                ) from exc
        return _sesion


def etiquetar(imagen: Image.Image, tamano: tuple[int, int] | None = None) -> np.ndarray:
    """Clase de cada píxel, del tamaño `tamano` (por defecto, el de la imagen).

    Se amplían los LOGITS y después se decide, no al revés: ampliar las
    etiquetas ya decididas deja el contorno en escalera, y aquí el contorno es
    justo por donde se cose la prenda generada con la foto original.
    """
    import cv2

    ancho, alto = tamano or imagen.size
    sesion = _sesion_del_modelo()
    x = np.asarray(
        imagen.convert("RGB").resize((LADO_DEL_MODELO, LADO_DEL_MODELO), Image.Resampling.BILINEAR),
        dtype=np.float32,
    ) / 255.0
    x = ((x - _MEDIA) / _DESVIACION).transpose(2, 0, 1)[None]
    logits = sesion.run(None, {sesion.get_inputs()[0].name: x})[0][0]
    ampliados = np.stack(
        [cv2.resize(canal, (ancho, alto), interpolation=cv2.INTER_LINEAR) for canal in logits]
    )
    return ampliados.argmax(axis=0).astype(np.uint8)
