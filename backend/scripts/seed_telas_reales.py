"""Da de alta las telas REALES de la tienda, sacadas de sus fotografías.

Ejecutar desde `backend/`:

    python -m scripts.seed_telas_reales            # telas de medida directa, gratis
    python -m scripts.seed_telas_reales --con-ia   # + estampados reconstruidos (cuesta)

Idempotente: una tela que ya existe con el mismo nombre se actualiza, no se
duplica.

DE DÓNDE SALE CADA TELA
-----------------------
De tres fotos de móvil hechas en la tienda (`scripts/muestras/`): una estantería
de estampados y rayas, una de lisos, y un primer plano de un floral. Cada tela se
recorta de su rollo y se digitaliza con `app/textil/digitalizar.py`:

- **Rayas y lisos**: se MIDEN —color, período, proporción— y el mosaico se
  reconstruye limpio con esas medidas. El balance de blancos se corrige por
  FOTO, con un blanco de referencia de la propia foto: las franjas blancas de
  las rayas y la tela blanca de los lisos.
- **Floral**: la foto cubre bastante tela, así que el mosaico ES la foto, con
  la luz quitada y la junta cerrada por corte de mínimo error.
- **Estampados tropicales**: de cada rollo solo se ve una franja de dos dedos
  de un dibujo que mide un palmo. No hay información para reconstruirlo de forma
  determinista, así que lo completa la IA — y la ficha dice que es una
  reconstrucción. El resultado se guarda en `scripts/muestras/reconstruidos/`
  para que volver a cargar el catálogo no cueste otra vez.

LO QUE NO SE INVENTA
--------------------
Composición, gramaje, ancho de rollo y precio. No se pueden leer en una foto y
la ficha es lo que el cliente usa para comprar: van vacíos, y la tienda los
completa. Tampoco se da de alta el rollo color vino: está en sombra total en la
foto, y el color que no llegó al sensor no se recupera.
"""

from __future__ import annotations

import io
import pathlib
import sys

import numpy as np
from PIL import Image
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.fabric import Fabric, FabricPattern
from app.services.storage import FOLDER_FABRICS, get_storage
from app.textil import digitalizar as dig
from app.textil.tejido_ia import hacer_repetible, medir_junta, reconstruir_estampado

MUESTRAS = pathlib.Path(__file__).parent / "muestras"
RECONSTRUIDOS = MUESTRAS / "reconstruidos"

ESTANTERIA = "estanteria_estampados_y_rayas.webp"
LISOS = "estanteria_lisos.webp"
FLORAL = "floral_acuarela.webp"

POR_CONFIRMAR = (
    "Composición, gramaje, ancho y precio por confirmar en tienda: no se pueden "
    "leer en una fotografía y no se inventan."
)

#: Cada entrada: la ficha, de qué foto sale, qué recorte se MIDE y cuál se
#: enseña como foto de catálogo (más amplio, con el rollo y sus dobleces).
RAYAS = [
    ("Raya ancha azul rey y blanco", "RAY-AZ-BL", "Azul rey y blanco", (250, 950, 880, 972), (60, 936, 899, 982)),
    ("Raya ancha rojo y blanco", "RAY-RO-BL", "Rojo y blanco", (250, 988, 880, 1016), (60, 978, 899, 1024)),
    ("Raya ancha verde salvia y blanco", "RAY-VS-BL", "Verde salvia y blanco", (250, 1158, 880, 1186), (60, 1146, 899, 1196)),
    ("Raya ancha chocolate y blanco", "RAY-CH-BL", "Chocolate y blanco", (250, 1400, 880, 1428), (60, 1380, 899, 1436)),
    ("Raya ancha fucsia y naranja", "RAY-FU-NA", "Fucsia y naranja", (250, 1506, 880, 1540), (60, 1494, 899, 1552)),
]

LISAS = [
    ("Tela lisa negra", "LIS-NE", "Negro", (150, 300, 500, 350), (0, 250, 899, 420)),
    ("Tela lisa rosa palo", "LIS-RP", "Rosa palo", (100, 440, 850, 490), (0, 360, 899, 560)),
    ("Tela lisa roja", "LIS-RO", "Rojo", (100, 590, 850, 670), (0, 520, 899, 720)),
    ("Tela lisa blanca", "LIS-BL", "Blanco", (100, 770, 850, 860), (0, 700, 899, 930)),
    ("Tela lisa marfil", "LIS-MA", "Marfil", (100, 990, 850, 1060), (0, 930, 899, 1110)),
    ("Tela lisa verde hierba", "LIS-VE", "Verde hierba", (100, 1350, 850, 1430), (0, 1310, 899, 1480)),
]

#: (nombre, referencia, color, franja que se ve del rollo, cómo se describe al modelo)
RECONSTRUCCIONES = [
    (
        "Estampado palmeras sobre azul (reconstruido)", "EST-PA-AZ", "Azul cielo y crudo",
        (0, 584, 899, 628),
        "printed fabric with pale cream palm leaves on a bright sky-blue ground",
    ),
    (
        "Estampado geométrico terracota (reconstruido)", "EST-GE-TE", "Terracota y crudo",
        (0, 758, 899, 802),
        "printed fabric with a cream aztec-style geometric zigzag and diamond pattern "
        "on a terracotta ground",
    ),
]


def main() -> int:
    con_ia = "--con-ia" in sys.argv
    almacen = get_storage()
    estanteria = Image.open(MUESTRAS / ESTANTERIA).convert("RGB")
    lisos = Image.open(MUESTRAS / LISOS).convert("RGB")
    floral = Image.open(MUESTRAS / FLORAL).convert("RGB")

    altas: list[dict] = []

    # --- Rayas: balance de blancos con las franjas que de verdad son blancas.
    medidas = [dig.medir_rayas(estanteria.crop(c)) for *_, c, _ in RAYAS]
    blancas = [m["claro"] for m in medidas if _saturacion(m["claro"]) < dig.SATURACION_DEL_BLANCO]
    ganancia = dig.ganancias_de_blanco(np.median(np.stack(blancas), axis=0))
    print(f"Rayas: balance de blancos {ganancia.round(3)} con {len(blancas)} franjas blancas.")

    for (nombre, ref, color, _, foto), medida in zip(RAYAS, medidas):
        medida = {
            **medida,
            "oscuro": dig.aplicar_ganancias(medida["oscuro"], ganancia),
            "claro": dig.aplicar_ganancias(medida["claro"], ganancia),
        }
        medida = dig.exponer_con_su_blanco(medida)
        altas.append({
            "name": nombre,
            "reference": ref,
            "description": (
                "Raya ancha de franjas iguales, tipo raya náutica o de toldo. "
                f"Colores medidos en la foto del rollo. {POR_CONFIRMAR}"
            ),
            "color_name": color,
            "color_hex": _hex(medida["oscuro"]),
            "pattern": FabricPattern.STRIPES,
            # El mosaico lleva 4 rayas; 3 mosaicos a lo ancho son 12 rayas en
            # una prenda de medio metro, unos 4 cm por raya, que es lo que mide
            # una raya ancha.
            "default_repeat": 3,
            "mosaico": dig.muestra_rayas(medida),
            "foto": _ficha(dig.muestra_rayas(medida), estanteria.crop(foto)),
        })

    # --- Lisos: balance de blancos con la tela blanca de la misma foto.
    colores = [dig.color_propio(lisos.crop(c)) for *_, c, _ in LISAS]
    blanco = colores[[n for n, *_ in LISAS].index("Tela lisa blanca")]
    ganancia = dig.ganancias_de_blanco(blanco)
    print(f"Lisos: balance de blancos {ganancia.round(3)} con la tela blanca.")

    for (nombre, ref, color, _, foto), medido in zip(LISAS, colores):
        corregido = dig.aplicar_ganancias(medido, ganancia)
        altas.append({
            "name": nombre,
            "reference": ref,
            "description": (
                "Tela lisa de caída suave y brillo apagado; por el aspecto, crepé o "
                f"viscosa. Color medido en la foto del rollo. {POR_CONFIRMAR}"
            ),
            "color_name": color,
            "color_hex": _hex(corregido),
            "pattern": FabricPattern.SOLID,
            "default_repeat": 8,
            "mosaico": dig.muestra_lisa(corregido),
            "foto": _ficha(dig.muestra_lisa(corregido), lisos.crop(foto)),
        })

    # --- Floral: la foto cubre tela de sobra, así que el mosaico ES la foto.
    recorte = floral.crop((0, 350, 899, 1249))
    # El fondo es un algodón claro y el móvil subexpuso la foto (mediana 147 de
    # 255): se usa ese fondo como referencia de blanco, como en las otras fotos.
    mosaico = dig.muestra_estampada(recorte, fondo_blanco=True)
    altas.append({
        "name": "Estampado floral acuarela",
        "reference": "EST-FL-AC",
        "description": (
            "Estampado floral en acuarela —ramas, hojas y bayas en rosa, salvia y "
            "ocre— sobre un tejido plano de hilo visible, tipo algodón o "
            f"lino-algodón. Mosaico sacado directamente de la foto. {POR_CONFIRMAR}"
        ),
        "color_name": "Crudo con flores rosa y salvia",
        "color_hex": _hex(np.median(np.asarray(mosaico, dtype=np.float32).reshape(-1, 3) / 255, axis=0)),
        "pattern": FabricPattern.PRINT,
        # Cada rama mide unos 3 cm y el mosaico lleva una docena: unos 25 cm
        # de tela, dos mosaicos en una prenda de medio metro.
        "default_repeat": 2,
        "mosaico": mosaico,
        "foto": _corregir(floral.crop((0, 200, 899, 1400)), recorte),
    })

    # --- Estampados reconstruidos por IA, con caché para no pagar dos veces.
    for nombre, ref, color, franja, descripcion in RECONSTRUCCIONES:
        # Se guarda la salida CRUDA del modelo, no el mosaico ya cerrado: si el
        # cierre de juntas mejora, se reprocesa sin volver a pagar.
        cache = RECONSTRUIDOS / f"{ref}.jpg"
        if cache.exists():
            crudo = Image.open(cache).convert("RGB")
            print(f"{nombre}: reconstrucción en caché.")
        elif con_ia:
            print(f"{nombre}: reconstruyendo con IA…")
            crudo, tokens = reconstruir_estampado(
                estanteria.crop(franja), descripcion, repetible=False
            )
            RECONSTRUIDOS.mkdir(parents=True, exist_ok=True)
            crudo.save(cache, format="JPEG", quality=95)
            print(f"   {tokens} tokens")
        else:
            print(f"{nombre}: se salta (hace falta --con-ia, y cuesta dinero).")
            continue
        mosaico = hacer_repetible(crudo)
        print(f"   junta {medir_junta(mosaico):.2f}")
        izquierda, arriba, derecha, abajo = franja
        altas.append({
            "name": nombre,
            "reference": ref,
            "description": (
                "Estampado RECONSTRUIDO con IA a partir de la franja que se ve del "
                "rollo en la estantería: mismos colores y estilo, pero no es el "
                f"dibujo exacto de la tela. {POR_CONFIRMAR}"
            ),
            "color_name": color,
            "color_hex": _hex(np.median(np.asarray(mosaico, dtype=np.float32).reshape(-1, 3) / 255, axis=0)),
            "pattern": FabricPattern.PRINT,
            "default_repeat": 2,
            "mosaico": mosaico,
            "foto": _ficha(mosaico, estanteria.crop((izquierda, max(0, arriba - 20), derecha, abajo + 20))),
        })

    _guardar(altas, almacen)
    return 0


def _guardar(altas: list[dict], almacen) -> None:
    with SessionLocal() as sesion:
        for alta in altas:
            mosaico = alta.pop("mosaico")
            foto = alta.pop("foto")
            tela = sesion.execute(select(Fabric).where(Fabric.name == alta["name"])).scalar_one_or_none()
            nueva = tela is None
            if nueva:
                tela = Fabric(**alta)
                sesion.add(tela)
            else:
                for campo, valor in alta.items():
                    setattr(tela, campo, valor)

            viejas = {tela.texture_key, tela.photo_key} - {None}
            tela.texture_key = almacen.save(_png(mosaico), folder=FOLDER_FABRICS, extension=".png")
            tela.photo_key = almacen.save(_jpg(foto), folder=FOLDER_FABRICS, extension=".jpg")
            sesion.commit()
            for clave in viejas:
                almacen.delete(clave)

            print(f"  {'alta' if nueva else 'actualizada'}: {tela.name} ({tela.color_hex})")


#: Lado de la foto de ficha compuesta.
LADO_FICHA = 800


def _ficha(mosaico: Image.Image, rollo: Image.Image) -> Image.Image:
    """Foto de catálogo cuadrada: la tela limpia arriba y el rollo real debajo.

    La tarjeta del catálogo es cuadrada y recorta con `object-cover`. Una tira
    de 839x46 —el lomo del rollo en la estantería, que es lo que hay— se
    ampliaba cinco veces en vertical y salía como una mancha. Así la ficha
    enseña la tela entera y, debajo, cómo se ve el rollo de verdad en la tienda.
    """
    lienzo = Image.new("RGB", (LADO_FICHA, LADO_FICHA), (255, 255, 255))
    tira_alto = max(24, round(rollo.height * LADO_FICHA / rollo.width))
    tira_alto = min(tira_alto, LADO_FICHA // 4)
    tela_alto = LADO_FICHA - tira_alto - 8
    lienzo.paste(
        mosaico.resize((LADO_FICHA, LADO_FICHA), Image.Resampling.LANCZOS).crop((0, 0, LADO_FICHA, tela_alto)),
        (0, 0),
    )
    lienzo.paste(rollo.resize((LADO_FICHA, tira_alto), Image.Resampling.LANCZOS), (0, tela_alto + 8))
    return lienzo


def _corregir(foto: Image.Image, referencia: Image.Image) -> Image.Image:
    """La foto de catálogo, con el mismo balance de blancos que su mosaico.

    Si no, la ficha enseñaría la foto gris del móvil al lado de un mosaico
    corregido, y parecerían dos telas distintas.
    """
    px = np.asarray(referencia.convert("RGB"), dtype=np.float32) / 255.0
    limpio = dig.quitar_luz(px, min(px.shape[:2]) * 0.25)
    ganancia = dig.ganancias_de_blanco(dig.color_de_fondo(limpio))
    foto_px = np.asarray(foto.convert("RGB"), dtype=np.float32) / 255.0
    return Image.fromarray(
        (np.clip(foto_px * ganancia[None, None, :], 0, 1) * 255).astype(np.uint8), mode="RGB"
    )


def _saturacion(color: np.ndarray) -> float:
    return float((color.max() - color.min()) / max(float(color.max()), 1e-3))


def _hex(color: np.ndarray) -> str:
    return "#" + "".join(f"{int(round(float(v) * 255)):02x}" for v in np.clip(color, 0, 1))


def _png(imagen: Image.Image) -> bytes:
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _jpg(imagen: Image.Image) -> bytes:
    buffer = io.BytesIO()
    imagen.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


if __name__ == "__main__":
    raise SystemExit(main())
