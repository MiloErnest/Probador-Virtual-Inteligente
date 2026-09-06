"""Carga datos de ejemplo en la base de datos.

Ejecutar desde la carpeta `backend/`:
    python -m scripts.seed

Es idempotente: si una prenda con el mismo nombre ya existe, no la duplica.
Las prendas se crean sin imagen; la interfaz muestra un marcador de posición
hasta que se suba una con POST /api/garments/{id}/image.
"""

from sqlalchemy import select

from app.core.database import SessionLocal, create_tables
from app.models.garment import Garment, GarmentCategory

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


def main() -> None:
    create_tables()

    created = 0
    skipped = 0

    with SessionLocal() as session:
        for data in SAMPLE_GARMENTS:
            exists = session.execute(
                select(Garment).where(Garment.name == data["name"])
            ).scalar_one_or_none()

            if exists is not None:
                skipped += 1
                continue

            session.add(Garment(**data))
            created += 1

        session.commit()

    print(f"Prendas creadas: {created} | ya existentes: {skipped}")


if __name__ == "__main__":
    main()
