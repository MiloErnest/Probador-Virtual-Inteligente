"""Carga datos de ejemplo en la base de datos.

Ejecutar desde la carpeta `backend/`:
    python -m scripts.seed

Es idempotente: si una prenda con el mismo nombre ya existe, no la duplica.

Por defecto las prendas se crean SIN imagen. Para generar siluetas de ejemplo
y que el probador virtual se pueda usar de inmediato:

    python -m scripts.seed --with-images

Son dibujos planos hechos con Pillow, no fotografías de producto: sirven para
demostrar el circuito completo sin depender de material con derechos. Para
usar imágenes reales, súbelas con POST /api/garments/{id}/image.
"""

import argparse
import io

from PIL import Image, ImageDraw
from sqlalchemy import select

from app.core.database import SessionLocal, get_schema_revision
from app.models.garment import Garment, GarmentCategory
from app.services.storage import FOLDER_GARMENTS, get_storage

SAMPLE_GARMENTS: list[dict] = [
    {
        "name": "Vestido largo de gala",
        "description": "Vestido de gala con falda amplia y escote en V.",
        "category": GarmentCategory.DRESS,
    },
    {
        "name": "Vestido midi plisado",
        "description": "Corte midi con plisado vertical y cintura marcada.",
        "category": GarmentCategory.DRESS,
    },
    {
        "name": "Camisa de lino",
        "description": "Camisa holgada de lino con cuello clásico.",
        "category": GarmentCategory.TOP,
    },
    {
        "name": "Blusa de seda",
        "description": "Blusa fluida de seda con caída marcada.",
        "category": GarmentCategory.TOP,
    },
    {
        "name": "Pantalón wide leg",
        "description": "Pantalón de pierna ancha y tiro alto.",
        "category": GarmentCategory.BOTTOM,
    },
    {
        "name": "Falda plisada",
        "description": "Falda plisada a media pierna.",
        "category": GarmentCategory.BOTTOM,
    },
    {
        "name": "Blazer estructurado",
        "description": "Blazer de hombro estructurado y solapa ancha.",
        "category": GarmentCategory.OUTERWEAR,
    },
    {
        "name": "Abrigo largo de lana",
        "description": "Abrigo recto de lana, largo por debajo de la rodilla.",
        "category": GarmentCategory.OUTERWEAR,
    },
]


# Silueta aproximada de cada categoría, dibujada sobre lienzo transparente.
# El fondo transparente importa: el proveedor de vista previa compone la
# prenda sobre la foto usando su canal alfa, así que un rectángulo opaco
# taparía a la persona entera.
CATEGORY_COLORS: dict[GarmentCategory, str] = {
    GarmentCategory.DRESS: "#8b5cf6",
    GarmentCategory.TOP: "#0ea5e9",
    GarmentCategory.BOTTOM: "#f59e0b",
    GarmentCategory.OUTERWEAR: "#10b981",
    GarmentCategory.OTHER: "#64748b",
}


def draw_garment(category: GarmentCategory) -> bytes:
    """Dibuja una silueta plana de la categoría y devuelve un PNG con alfa."""
    width, height = 400, 500
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    color = CATEGORY_COLORS[category]

    if category is GarmentCategory.BOTTOM:
        # Dos perneras unidas por la cintura.
        draw.polygon(
            [(110, 40), (290, 40), (280, 470), (215, 470), (200, 230),
             (185, 470), (120, 470)],
            fill=color,
        )
    elif category is GarmentCategory.DRESS:
        # Cuerpo estrecho que se abre en falda.
        draw.polygon(
            [(150, 60), (250, 60), (270, 200), (330, 470), (70, 470), (130, 200)],
            fill=color,
        )
        draw.polygon([(150, 60), (110, 150), (140, 160)], fill=color)  # manga izq.
        draw.polygon([(250, 60), (290, 150), (260, 160)], fill=color)  # manga der.
    else:
        # Prenda superior: torso con dos mangas.
        draw.polygon([(140, 70), (260, 70), (265, 380), (135, 380)], fill=color)
        draw.polygon([(140, 70), (85, 200), (130, 215), (140, 130)], fill=color)
        draw.polygon([(260, 70), (315, 200), (270, 215), (260, 130)], fill=color)
        # Cuello.
        draw.ellipse([(175, 55), (225, 90)], fill=(0, 0, 0, 0))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def main() -> None:
    # Antes creaba las tablas por su cuenta con `create_all`. Desde la Etapa 2
    # el esquema es responsabilidad de Alembic, y un script de datos no debe
    # tener la potestad de inventarse un esquema paralelo. Si la base no está
    # migrada, se dice qué hacer en vez de fallar con un error de SQL opaco.
    if get_schema_revision() is None:
        raise SystemExit(
            "La base de datos no tiene migraciones aplicadas.\n"
            "Ejecuta primero, desde la carpeta backend/:  alembic upgrade head"
        )

    parser = argparse.ArgumentParser(description="Carga el catálogo de ejemplo.")
    parser.add_argument(
        "--with-images",
        action="store_true",
        help="Genera siluetas de ejemplo para las prendas que no tengan imagen.",
    )
    args = parser.parse_args()

    created = 0
    skipped = 0
    imaged = 0

    storage = get_storage()

    with SessionLocal() as session:
        for data in SAMPLE_GARMENTS:
            garment = session.execute(
                select(Garment).where(Garment.name == data["name"])
            ).scalar_one_or_none()

            if garment is None:
                garment = Garment(**data)
                session.add(garment)
                created += 1
            else:
                skipped += 1

            # Solo se genera si falta: así el script sigue siendo idempotente
            # y no pisa una fotografía real que se hubiera subido antes.
            if args.with_images and not garment.image_key:
                session.flush()  # asigna el id antes de guardar el archivo
                garment.image_key = storage.save(
                    draw_garment(garment.category),
                    folder=FOLDER_GARMENTS,
                    extension=".png",
                )
                imaged += 1

        session.commit()

    print(f"Prendas creadas: {created} | ya existentes: {skipped}")
    if args.with_images:
        print(f"Imágenes generadas: {imaged}")
    elif created or skipped:
        print("Sin imágenes. Para generarlas:  python -m scripts.seed --with-images")


if __name__ == "__main__":
    main()
