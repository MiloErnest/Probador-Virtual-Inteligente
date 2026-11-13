"""Repite la composición de las pruebas sobre persona ya guardadas.

CUÁNDO SE EJECUTA ESTO
----------------------
Cuando `app/probador/conservar.py` o `vestir.py` mejoran. Una prueba sobre
persona son dos pasos: el modelo de Hugging Face viste a la persona (lento, y
gasta cuota), y después la composición decide qué se toma de esa imagen y qué
vuelve a ser la foto (rápido, y gratis). Desde el 10/11/2026 cada prueba
guarda lo que devolvió el modelo, sin componer, y la caja de la foto a la que
corresponde. Con eso, este script rehace SOLO el segundo paso.

No llama a Hugging Face. No gasta cuota.

QUÉ TOCA Y QUÉ NO
-----------------
Sin `--aplicar` no escribe nada: dice, prueba por prueba, cuánto cambiaría el
resultado. Con `--aplicar` sustituye la imagen del resultado, el aviso y la
fracción editada. La foto de la persona, la prenda y la salida cruda del
modelo no se tocan nunca: son los datos de los que sale todo lo demás.

Las pruebas anteriores al 10/11/2026 no tienen salida cruda y se saltan: para
mejorarlas hay que repetirlas con el modelo.

    python -m scripts.recomponer                 # qué cambiaría, sin tocar nada
    python -m scripts.recomponer --aplicar       # todas las que tengan salida cruda
    python -m scripts.recomponer --aplicar 25    # solo la prueba 25
"""

from __future__ import annotations

import io
import sys

import numpy as np
from PIL import Image

from app.core.database import SessionLocal
from app.models.fabric_trial import TrialStatus
from app.models.person_photo import PersonPhoto
from app.models.try_on import TryOn
from app.probador import recomponer
from app.services.storage import FOLDER_TRY_ONS, get_storage
from app.textil import ErrorDeMotor


def main() -> int:
    aplicar = "--aplicar" in sys.argv
    solo = {int(a) for a in sys.argv[1:] if a.isdigit()}

    sesion = SessionLocal()
    # El mismo punto de construcción que usa la aplicación.
    almacen = get_storage()

    def abrir(clave: str) -> Image.Image:
        imagen = Image.open(io.BytesIO(almacen.read(clave)))
        imagen.load()
        return imagen

    try:
        pruebas = sesion.query(TryOn).order_by(TryOn.id).all()
        if solo:
            pruebas = [p for p in pruebas if p.id in solo]
        if not pruebas:
            print("No hay pruebas sobre persona que recomponer.")
            return 0

        print(f"{len(pruebas)} prueba(s). {'APLICANDO' if aplicar else 'Simulacro'}.\n")
        cambiadas = 0

        for prueba in pruebas:
            if prueba.status is not TrialStatus.COMPLETED or not prueba.output_image_key:
                print(f"  #{prueba.id}: no está terminada. Se salta.")
                continue
            if not (prueba.raw_output_key and prueba.raw_box and prueba.garment_image_key):
                print(f"  #{prueba.id}: no guarda la salida del modelo (es anterior). Se salta.")
                continue
            foto = sesion.get(PersonPhoto, prueba.person_photo_id)
            try:
                persona = abrir(foto.image_key).convert("RGB")
                cruda = abrir(prueba.raw_output_key)
                prenda = abrir(prueba.garment_image_key)
                actual = abrir(prueba.output_image_key).convert("RGB")
            except (FileNotFoundError, AttributeError):
                print(f"  #{prueba.id}: falta alguno de sus archivos. Se salta.")
                continue

            caja = tuple(int(v) for v in prueba.raw_box.split(","))
            try:
                vestida = recomponer(
                    persona,
                    caja,
                    cruda,
                    prenda,
                    prueba.category,
                    proveedor=prueba.provider or "",
                    parametros=prueba.model_params,
                )
            except ErrorDeMotor as exc:
                print(f"  #{prueba.id}: la composición nueva la rechaza ({exc}). Se deja como está.")
                continue

            # Cuánto cambia: fracción de la foto con una diferencia que se ve.
            distinto = np.abs(
                np.asarray(vestida.imagen, dtype=np.int16) - np.asarray(actual, dtype=np.int16)
            ).max(axis=2)
            print(
                f"  #{prueba.id} ({prueba.category.value}): cambia un "
                f"{(distinto > 24).mean():.1%} de la foto | editado "
                f"{prueba.edited_fraction or 0:.4f} -> {vestida.editado:.4f}"
            )

            if not aplicar:
                continue

            buffer = io.BytesIO()
            vestida.imagen.save(buffer, format="JPEG", quality=92, optimize=True)
            clave_vieja = prueba.output_image_key
            prueba.output_image_key = almacen.save(
                buffer.getvalue(), folder=FOLDER_TRY_ONS, extension=".jpg"
            )
            prueba.edited_fraction = round(vestida.editado, 4)
            prueba.notice = vestida.aviso or None
            sesion.add(prueba)
            cambiadas += 1

            # La nueva ya está escrita y referenciada: si el borrado falla,
            # queda un archivo huérfano, no una prueba sin imagen.
            if clave_vieja:
                almacen.delete(clave_vieja)

        if aplicar:
            sesion.commit()
            print(f"\n{cambiadas} prueba(s) recompuestas.")
        else:
            print("\nNada escrito. Repite con --aplicar.")
        return 0
    finally:
        sesion.close()


if __name__ == "__main__":
    raise SystemExit(main())
