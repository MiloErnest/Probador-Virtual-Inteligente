"""Sustituye el mosaico procedural de una tela por uno fotográfico, con IA.

QUÉ HACE Y POR QUÉ ESTÁ AQUÍ Y NO EN UNA PETICIÓN
--------------------------------------------------
El mosaico de una tela es un dato del catálogo, no de una prueba. Se genera una
vez, se guarda, y a partir de ahí lo usan todas las pruebas de todos los
usuarios — con el motor determinista, que conserva la geometría exacta de la
prenda porque es una multiplicación por píxel.

Ese reparto es lo que resuelve el problema de fondo: la IA hace lo que sabe
hacer (que un trozo de tela parezca tela) y no toca lo que no debe (la prenda).

CUESTA DINERO. Por eso:
  - no hace nada sin `--aplicar`;
  - dice de antemano cuántas llamadas va a hacer;
  - guarda una comparativa para poder mirar antes de fiarse;
  - conserva el mosaico anterior si el nuevo sale peor de lo que estaba.

    python -m scripts.telas_fotograficas                    # simulacro
    python -m scripts.telas_fotograficas --telas 12 --aplicar
    python -m scripts.telas_fotograficas --aplicar          # las doce
"""

from __future__ import annotations

import io
import sys
import time

from PIL import Image

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.fabric import Fabric
from app.services.fabric_trial import _describir
from app.services.storage import FOLDER_FABRICS, get_storage
from app.textil.errores import ErrorDeMotor
from app.textil.tejido_ia import medir_junta, sintetizar_mosaico

#: Por encima de esto, la unión del mosaico se nota al repetir y no se guarda.
#: Un mosaico bien cerrado da ~1: el salto entre sus bordes opuestos es como el
#: salto entre dos columnas cualesquiera de dentro.
JUNTA_MAXIMA = 2.5


def main() -> int:
    argumentos = sys.argv[1:]
    aplicar = "--aplicar" in argumentos

    elegidas: list[int] | None = None
    if "--telas" in argumentos:
        crudo = argumentos[argumentos.index("--telas") + 1]
        elegidas = [int(x) for x in crudo.replace(",", " ").split()]

    sesion = SessionLocal()
    almacen = get_storage()
    try:
        consulta = sesion.query(Fabric).order_by(Fabric.id)
        telas = [t for t in consulta.all() if elegidas is None or t.id in elegidas]
        if not telas:
            print("No hay telas que procesar.")
            return 1

        print(f"Modelo: {settings.OPENAI_TEXTURE_MODEL} "
              f"(calidad {settings.OPENAI_TEXTURE_QUALITY})")
        print(f"{len(telas)} tela(s). {'APLICANDO' if aplicar else 'Simulacro'}.\n")

        if not aplicar:
            for tela in telas:
                print(f"  #{tela.id} {tela.name}")
                print(f"      -> «{_describir(tela)}»")
            print(f"\nSerían {len(telas)} llamada(s) de pago. Repite con --aplicar.")
            return 0

        hechas, tokens_totales = 0, 0
        for tela in telas:
            anterior = None
            if tela.texture_key:
                anterior = Image.open(io.BytesIO(almacen.read(tela.texture_key)))
                anterior.load()

            descripcion = _describir(tela)
            print(f"  #{tela.id} {tela.name}")
            comenzado = time.perf_counter()
            try:
                mosaico, tokens = sintetizar_mosaico(descripcion, anterior)
            except ErrorDeMotor as exc:
                print(f"      FALLO: {exc}")
                continue
            ms = (time.perf_counter() - comenzado) * 1000

            junta = medir_junta(mosaico)
            print(f"      {ms:.0f} ms · {tokens} tokens · junta {junta:.2f}")

            if junta > JUNTA_MAXIMA:
                print("      SE DESCARTA: la unión se notaría al repetir.")
                continue

            buffer = io.BytesIO()
            mosaico.save(buffer, format="PNG", optimize=True)
            clave_vieja = tela.texture_key
            tela.texture_key = almacen.save(
                buffer.getvalue(), folder=FOLDER_FABRICS, extension=".png"
            )
            sesion.add(tela)
            sesion.commit()
            if clave_vieja:
                almacen.delete(clave_vieja)

            hechas += 1
            tokens_totales += tokens or 0

        print(f"\n{hechas} mosaico(s) actualizados · {tokens_totales} tokens en total.")
        return 0
    finally:
        sesion.close()


if __name__ == "__main__":
    raise SystemExit(main())
