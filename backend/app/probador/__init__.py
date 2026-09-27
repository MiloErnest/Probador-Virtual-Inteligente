"""El probador: la persona de la foto, con una prenda del taller puesta.

- `prenda.py`     la prenda recortada del taller, los mismos píxeles.
- `partes.py`     qué es cada píxel de una persona (analizador en CPU).
- `proveedor.py`  el contrato del modelo y el selector.
- `fashn.py`      FASHN VTON 1.5 en su Space gratuito de Hugging Face.
- `conservar.py`  qué se toma del modelo y qué vuelve a ser la foto original.
- `vestir.py`     el camino entero.

Igual que el motor textil, no conoce los servicios: lanza `ErrorDeMotor` y el
servicio lo traduce.
"""

from app.probador.prenda import recortar_prenda
from app.probador.vestir import PersonaVestida, vestir_persona

__all__ = ["PersonaVestida", "recortar_prenda", "vestir_persona"]
