"""Carga un catálogo de telas de ejemplo.

Ejecutar desde la carpeta `backend/`:
    python -m scripts.seed_telas

Es idempotente: una tela que ya existe con el mismo nombre no se duplica, y su
mosaico solo se genera si le falta.

DE DÓNDE SALEN ESTAS TELAS
--------------------------
Los mosaicos se dibujan con funciones periódicas (`scripts/tejidos.py`), así que
se repiten sin costura visible. Las fichas técnicas —composición, gramaje,
ancho, precio— son valores realistas del sector, no datos de ningún proveedor
concreto.

El objetivo es que el catálogo funcione desde el primer arranque. Para el
producto real, la tienda textil aliada fotografía sus rollos y se recorta un
cuadrado limpio de cada uno: sale mejor que cualquier simulación y es gratis.
"""

import io

from sqlalchemy import select

from app.core.database import SessionLocal, get_schema_revision
from app.models.fabric import Fabric, FabricPattern
from app.services.storage import FOLDER_FABRICS, get_storage
from scripts import tejidos

#: (nombre, referencia, ficha, dibujo, cómo se dibuja el mosaico, repeticiones)
#:
#: `default_repeat` es cuántas veces se repite el mosaico a lo ancho de una
#: prenda, y es la escala del estampado. En un liso da igual; en un cuadro
#: escocés es la diferencia entre una camisa y un mantel.
TELAS: list[dict] = [
    {
        "name": "Popelín de algodón blanco",
        "reference": "POP-100-BL",
        "description": "Popelín fino de algodón peinado, tacto seco y buena caída.",
        "composition": "100% algodón",
        "weight_gsm": 120,
        "width_cm": 150,
        "price_per_meter": 8.90,
        "color_name": "Blanco óptico",
        "color_hex": "#f2f1ee",
        "pattern": FabricPattern.SOLID,
        "default_repeat": 9,
        "mosaico": lambda: tejidos.tafetan((242, 241, 238)),
    },
    {
        "name": "Popelín de algodón azul francia",
        "reference": "POP-100-AZ",
        "description": "El mismo popelín, teñido en azul medio. Clásico de camisería.",
        "composition": "100% algodón",
        "weight_gsm": 120,
        "width_cm": 150,
        "price_per_meter": 8.90,
        "color_name": "Azul Francia",
        "color_hex": "#3a5c96",
        "pattern": FabricPattern.SOLID,
        "default_repeat": 9,
        "mosaico": lambda: tejidos.tafetan((58, 92, 150)),
    },
    {
        "name": "Lino lavado crudo",
        "reference": "LIN-100-CR",
        "description": "Lino lavado a la piedra, con el hilo irregular característico.",
        "composition": "100% lino",
        "weight_gsm": 190,
        "width_cm": 140,
        "price_per_meter": 16.50,
        "color_name": "Crudo",
        "color_hex": "#d6cab2",
        "pattern": FabricPattern.TEXTURED,
        "default_repeat": 7,
        "mosaico": lambda: tejidos.lino((214, 202, 178)),
    },
    {
        "name": "Lino lavado terracota",
        "reference": "LIN-100-TE",
        "description": "Lino de verano en tono tierra, muy fresco.",
        "composition": "100% lino",
        "weight_gsm": 190,
        "width_cm": 140,
        "price_per_meter": 16.50,
        "color_name": "Terracota",
        "color_hex": "#b06a4a",
        "pattern": FabricPattern.TEXTURED,
        "default_repeat": 7,
        "mosaico": lambda: tejidos.lino((176, 106, 74)),
    },
    {
        "name": "Denim 12 oz índigo",
        "reference": "DEN-12-IN",
        "description": "Sarga de algodón pesada, teñida en índigo. Para pantalón y cazadora.",
        "composition": "98% algodón, 2% elastano",
        "weight_gsm": 400,
        "width_cm": 150,
        "price_per_meter": 19.90,
        "color_name": "Índigo",
        "color_hex": "#2e4468",
        "pattern": FabricPattern.TEXTURED,
        "default_repeat": 6,
        "mosaico": lambda: tejidos.sarga((46, 68, 104)),
    },
    {
        "name": "Franela de lana gris marengo",
        "reference": "LAN-FR-GM",
        "description": "Franela de lana virgen en ligamento sarga. Caída de traje.",
        "composition": "100% lana virgen",
        "weight_gsm": 320,
        "width_cm": 150,
        "price_per_meter": 34.00,
        "color_name": "Gris marengo",
        "color_hex": "#4a4d52",
        "pattern": FabricPattern.TEXTURED,
        "default_repeat": 6,
        "mosaico": lambda: tejidos.sarga((74, 77, 82)),
    },
    {
        "name": "Vichy rojo",
        "reference": "VIC-CU-RO",
        "description": "Cuadro vichy clásico, tejido en hilo teñido. No estampado.",
        "composition": "100% algodón",
        "weight_gsm": 130,
        "width_cm": 145,
        "price_per_meter": 10.50,
        "color_name": "Rojo y blanco",
        "color_hex": "#963c39",
        "pattern": FabricPattern.CHECKS,
        "default_repeat": 8,
        "mosaico": lambda: tejidos.cuadros((236, 232, 224), (150, 40, 45)),
    },
    {
        "name": "Vichy azul marino",
        "reference": "VIC-CU-AM",
        "description": "El mismo vichy en azul. Cuadro de un centímetro.",
        "composition": "100% algodón",
        "weight_gsm": 130,
        "width_cm": 145,
        "price_per_meter": 10.50,
        "color_name": "Marino y blanco",
        "color_hex": "#2c3f6b",
        "pattern": FabricPattern.CHECKS,
        "default_repeat": 8,
        "mosaico": lambda: tejidos.cuadros((236, 232, 224), (40, 60, 110)),
    },
    {
        "name": "Rayas marineras",
        "reference": "RAY-MA-01",
        "description": "Raya ancha en la dirección del hilo de urdimbre.",
        "composition": "100% algodón",
        "weight_gsm": 145,
        "width_cm": 150,
        "price_per_meter": 12.00,
        "color_name": "Marino y crudo",
        "color_hex": "#283c6e",
        "pattern": FabricPattern.STRIPES,
        "default_repeat": 7,
        "mosaico": lambda: tejidos.rayas((240, 238, 232), (40, 60, 110)),
    },
    {
        "name": "Punto de algodón gris jaspeado",
        "reference": "PUN-AL-GR",
        "description": "Género de punto de galga fina. Se estira, no se teje plano.",
        "composition": "95% algodón, 5% elastano",
        "weight_gsm": 210,
        "width_cm": 180,
        "price_per_meter": 14.00,
        "color_name": "Gris jaspeado",
        "color_hex": "#92929a",
        "pattern": FabricPattern.TEXTURED,
        "default_repeat": 10,
        "mosaico": lambda: tejidos.punto((146, 146, 154)),
    },
    {
        "name": "Punto de algodón verde oliva",
        "reference": "PUN-AL-VO",
        "description": "El mismo punto en verde militar.",
        "composition": "95% algodón, 5% elastano",
        "weight_gsm": 210,
        "width_cm": 180,
        "price_per_meter": 14.00,
        "color_name": "Verde oliva",
        "color_hex": "#5d6647",
        "pattern": FabricPattern.TEXTURED,
        "default_repeat": 10,
        "mosaico": lambda: tejidos.punto((93, 102, 71)),
    },
    {
        "name": "Tafetán de seda burdeos",
        "reference": "SED-TA-BU",
        "description": "Seda natural de tafetán, con cuerpo y brillo.",
        "composition": "100% seda",
        "weight_gsm": 90,
        "width_cm": 140,
        "price_per_meter": 42.00,
        "color_name": "Burdeos",
        "color_hex": "#6d2431",
        "pattern": FabricPattern.SOLID,
        "default_repeat": 11,
        "mosaico": lambda: tejidos.tafetan((109, 36, 49)),
    },
]


def main() -> None:
    if get_schema_revision() is None:
        raise SystemExit(
            "La base de datos no tiene migraciones aplicadas.\n"
            "Ejecuta primero, desde la carpeta backend/:  alembic upgrade head"
        )

    storage = get_storage()
    creadas = existentes = mosaicos = 0

    with SessionLocal() as session:
        for datos in TELAS:
            dibujar = datos["mosaico"]
            campos = {k: v for k, v in datos.items() if k != "mosaico"}

            tela = session.execute(
                select(Fabric).where(Fabric.name == campos["name"])
            ).scalar_one_or_none()

            if tela is None:
                tela = Fabric(**campos)
                session.add(tela)
                creadas += 1
            else:
                existentes += 1

            # Solo se genera si falta: así el script sigue siendo idempotente y
            # no pisa una fotografía real que se hubiera subido antes.
            if not tela.texture_key:
                session.flush()
                buffer = io.BytesIO()
                dibujar().save(buffer, format="PNG", optimize=True)
                clave = storage.save(
                    buffer.getvalue(), folder=FOLDER_FABRICS, extension=".png"
                )
                # El mosaico sirve también de foto de catálogo mientras no haya
                # una de verdad: enseña el tejido, que es lo que importa.
                tela.texture_key = clave
                if not tela.photo_key:
                    tela.photo_key = clave
                mosaicos += 1

        session.commit()

    print(f"Telas creadas: {creadas} | ya existentes: {existentes}")
    print(f"Mosaicos generados: {mosaicos}")


if __name__ == "__main__":
    main()
