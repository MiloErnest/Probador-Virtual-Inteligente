"""Motor textil: vestir una prenda con una tela.

Dos piezas y una costura:

- `segmentar.py`  qué píxeles son prenda. Se calcula una vez por imagen subida.
- `retexturizar.py`  el motor determinista: reutiliza la luz de la fotografía.
- `provider.py`  el contrato y el selector. Un motor desconocido falla en voz
  alta; nunca cae al local en silencio.
- `openai_provider.py`  el motor generativo, para bocetos.
"""

from app.textil.errores import ErrorDeMotor
from app.textil.provider import (
    MotorDeTela,
    MotorRetexturizado,
    PeticionDeTela,
    ResultadoDeTela,
    motor_para,
)
from app.textil.retexturizar import retexturizar
from app.textil.segmentar import Recorte, segmentar_prenda

__all__ = [
    "ErrorDeMotor",
    "MotorDeTela",
    "MotorRetexturizado",
    "PeticionDeTela",
    "ResultadoDeTela",
    "motor_para",
    "retexturizar",
    "Recorte",
    "segmentar_prenda",
]
