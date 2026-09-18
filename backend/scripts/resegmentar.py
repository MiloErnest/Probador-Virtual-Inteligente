"""Recalcula el recorte de las prendas ya subidas.

CUÁNDO SE EJECUTA ESTO
----------------------
Cuando `app/textil/segmentar.py` mejora. El recorte se calcula UNA vez, al
subir, y se guarda: eso es lo correcto —se necesita idéntico para cada tela que
se pruebe, y recalcularlo en cada prueba haría que dos telas de la misma prenda
no fueran comparables—, pero tiene la contrapartida de que una mejora del
recorte no alcanza sola a lo que ya está subido.

Se escribió al añadir la exclusión de la figura: sin pasar esto, los bocetos ya
subidos seguían saliendo con la tela estampada en la cara de la modelo.

QUÉ TOCA Y QUÉ NO
-----------------
Reescribe la máscara y sus tres campos derivados. **No toca la imagen original
del usuario**, que es el dato de verdad; la máscara siempre se puede volver a
deducir de ella, que es justo lo que hace este script.

Las pruebas ya generadas se quedan como están: son el historial, y reescribirlo
sería mentir sobre lo que se vio en su momento.

    python -m scripts.resegmentar            # dice qué haría, sin tocar nada
    python -m scripts.resegmentar --aplicar
"""

from __future__ import annotations

import io
import sys

from PIL import Image

from app.core.database import SessionLocal
from app.models.garment_upload import GarmentUpload
from app.services.storage import get_storage
from app.textil.segmentar import segmentar_prenda

CARPETA_MASCARAS = "masks"


def main() -> int:
    aplicar = "--aplicar" in sys.argv

    sesion = SessionLocal()
    # El mismo punto de construcción que usa la aplicación: si mañana el
    # almacén es remoto, este script lo sigue sin enterarse.
    almacen = get_storage()
    try:
        prendas = sesion.query(GarmentUpload).order_by(GarmentUpload.id).all()
        if not prendas:
            print("No hay prendas subidas.")
            return 0

        print(f"{len(prendas)} prenda(s). {'APLICANDO' if aplicar else 'Simulacro'}.\n")
        cambiadas = 0

        for prenda in prendas:
            try:
                imagen = Image.open(io.BytesIO(almacen.read(prenda.image_key)))
                imagen.load()
            except FileNotFoundError:
                print(f"  #{prenda.id} {prenda.name}: falta el archivo original. Se salta.")
                continue

            recorte = segmentar_prenda(imagen)
            antes = prenda.mask_coverage or 0.0
            delta = recorte.cobertura - antes

            print(
                f"  #{prenda.id} {prenda.name} ({prenda.kind.value}): "
                f"cobertura {antes:.4f} -> {recorte.cobertura:.4f} ({delta:+.4f})"
                + ("  DUDOSO" if recorte.dudoso else "")
            )

            if not aplicar:
                continue

            buffer = io.BytesIO()
            recorte.mascara.save(buffer, format="PNG", optimize=True)
            clave_vieja = prenda.mask_key

            prenda.mask_key = almacen.save(
                buffer.getvalue(), folder=CARPETA_MASCARAS, extension=".png"
            )
            prenda.mask_coverage = recorte.cobertura
            prenda.mask_suspect = recorte.dudoso
            sesion.add(prenda)
            cambiadas += 1

            # La nueva ya está escrita y referenciada: si el borrado falla, se
            # queda un archivo huérfano, que es mucho mejor que una prenda
            # apuntando a una máscara que ya no existe.
            if clave_vieja:
                almacen.delete(clave_vieja)

        if aplicar:
            sesion.commit()
            print(f"\n{cambiadas} recorte(s) actualizados.")
        else:
            print("\nNada escrito. Repite con --aplicar.")
        return 0
    finally:
        sesion.close()


if __name__ == "__main__":
    raise SystemExit(main())
