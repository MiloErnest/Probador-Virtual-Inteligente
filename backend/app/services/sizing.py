"""Recomendación de talla a partir de las medidas del usuario (Fase 3).

ESTO NO ES UN SIMULADO
----------------------
A diferencia del análisis corporal y del generador de diseños, aquí no hay
nada que aplazar: recomendar talla es comparar medidas contra una tabla, y eso
se puede hacer bien hoy. Lo que sí es aproximado es de dónde salen las
medidas, no el cálculo.

QUÉ MEDIDA MANDA SEGÚN LA PRENDA
--------------------------------
No todas las prendas se tallan igual. Una camisa se talla por pecho; un
pantalón, por cintura y cadera. Usar siempre la misma medida daría tallas
absurdas para la mitad del catálogo.

Cuando una prenda depende de varias medidas, se toma la talla MÁS GRANDE de
las candidatas. Es deliberado: una prenda holgada se puede ajustar, una que
no entra no sirve. En tallaje se llama "tallar por la medida mayor" y es la
práctica habitual.

LAS TABLAS SON GENÉRICAS
------------------------
Son rangos de tallaje europeo de uso común, no las de ninguna marca. Cada
fabricante talla distinto —y de ahí que la gente use tallas distintas según la
tienda—. El día que las prendas traigan su propia tabla, esta se queda como
la de reserva.
"""

from dataclasses import dataclass

from app.models.body_profile import BodyProfile
from app.models.garment import GarmentCategory

# Talla -> (mínimo, máximo) en centímetros, extremo superior incluido.
# Los extremos abiertos usan valores muy amplios para que ninguna medida real
# se quede sin talla: es preferible recomendar XXL y avisar, que no responder.
SizeChart = dict[str, tuple[float, float]]

CHEST_CHART: SizeChart = {
    "XS": (0.0, 82.0),
    "S": (82.0, 90.0),
    "M": (90.0, 98.0),
    "L": (98.0, 106.0),
    "XL": (106.0, 116.0),
    "XXL": (116.0, 999.0),
}

WAIST_CHART: SizeChart = {
    "XS": (0.0, 66.0),
    "S": (66.0, 74.0),
    "M": (74.0, 82.0),
    "L": (82.0, 90.0),
    "XL": (90.0, 100.0),
    "XXL": (100.0, 999.0),
}

HIPS_CHART: SizeChart = {
    "XS": (0.0, 88.0),
    "S": (88.0, 96.0),
    "M": (96.0, 104.0),
    "L": (104.0, 112.0),
    "XL": (112.0, 122.0),
    "XXL": (122.0, 999.0),
}

# Orden de menor a mayor. Es lo que permite decidir cuál de dos tallas es la
# más grande sin depender del orden de un diccionario.
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]

# Qué medidas manda cada categoría, en orden de importancia.
CATEGORY_MEASUREMENTS: dict[GarmentCategory, list[str]] = {
    GarmentCategory.TOP: ["chest"],
    GarmentCategory.OUTERWEAR: ["chest"],
    GarmentCategory.BOTTOM: ["waist", "hips"],
    # Un vestido cubre torso y cadera: hay que mirar las tres.
    GarmentCategory.DRESS: ["chest", "waist", "hips"],
    GarmentCategory.OTHER: ["chest"],
}

CHARTS: dict[str, SizeChart] = {
    "chest": CHEST_CHART,
    "waist": WAIST_CHART,
    "hips": HIPS_CHART,
}

MEASUREMENT_LABELS = {"chest": "pecho", "waist": "cintura", "hips": "cadera"}


@dataclass(frozen=True)
class SizeRecommendation:
    """Resultado de la recomendación.

    Incluye el porqué (`reason`, `based_on`) y no solo la talla: una
    recomendación que no se puede cuestionar es una que nadie se cree. Si el
    usuario ve que se calculó por su cintura, entiende por qué le sale L
    cuando él suele usar M.
    """

    size: str | None
    based_on: list[str]
    reason: str
    # Tallas que salen de cada medida por separado. Cuando no coinciden, la
    # prenda le quedará ajustada en unas zonas y holgada en otras, y eso es
    # información útil que merece la pena enseñar.
    per_measurement: dict[str, str]
    confidence: float


def size_for(value: float, chart: SizeChart) -> str:
    """Talla que corresponde a una medida dentro de una tabla."""
    for talla in SIZE_ORDER:
        minimo, maximo = chart[talla]
        if minimo < value <= maximo:
            return talla
    # Solo se llega aquí con una medida de 0 o negativa, que la validación de
    # entrada ya impide.
    return SIZE_ORDER[0]


def largest(sizes: list[str]) -> str:
    """La mayor de varias tallas. Una prenda holgada se ajusta; una que no
    entra, no sirve."""
    return max(sizes, key=SIZE_ORDER.index)


def recommend(profile: BodyProfile, category: GarmentCategory) -> SizeRecommendation:
    """Recomienda talla para una categoría, con lo que haya en el perfil."""
    necesarias = CATEGORY_MEASUREMENTS.get(category, ["chest"])

    disponibles: dict[str, float] = {}
    for nombre in necesarias:
        valor = getattr(profile, f"{nombre}_cm", None)
        if valor is not None and valor > 0:
            disponibles[nombre] = valor

    if not disponibles:
        faltan = ", ".join(MEASUREMENT_LABELS[n] for n in necesarias)
        return SizeRecommendation(
            size=None,
            based_on=[],
            reason=(
                f"Faltan medidas para calcular la talla de esta prenda: {faltan}. "
                "Añádelas en tu perfil corporal."
            ),
            per_measurement={},
            confidence=0.0,
        )

    por_medida = {n: size_for(v, CHARTS[n]) for n, v in disponibles.items()}
    talla = largest(list(por_medida.values()))

    etiquetas = [MEASUREMENT_LABELS[n] for n in disponibles]
    if len(set(por_medida.values())) > 1:
        detalle = ", ".join(
            f"{MEASUREMENT_LABELS[n]} → {t}" for n, t in por_medida.items()
        )
        razon = (
            f"Tus medidas dan tallas distintas ({detalle}). Se recomienda la mayor, "
            f"{talla}, porque una prenda holgada se puede ajustar y una que no entra, no."
        )
    else:
        # "pecho, cintura y cadera", no "pecho y cintura y cadera".
        if len(etiquetas) == 1:
            lista = etiquetas[0]
        else:
            lista = ', '.join(etiquetas[:-1]) + ' y ' + etiquetas[-1]
        razon = f'Calculada a partir de tu {lista}.'

    # La confianza baja si faltan medidas de las que la prenda necesita: con
    # media información, la recomendación vale menos y hay que decirlo.
    cobertura = len(disponibles) / len(necesarias)
    confianza = round(0.5 + 0.5 * cobertura, 2)
    #  puede ser None en un perfil recien construido y aun sin guardar:
    # el valor por defecto lo pone la base de datos, no Python.
    if profile.source is not None and profile.source.value == "analysis":
        # Medidas estimadas de una foto, no medidas tomadas con cinta.
        confianza = round(confianza * 0.6, 2)
        razon += " Ojo: parten de medidas estimadas por foto, no medidas a mano."

    return SizeRecommendation(
        size=talla,
        based_on=list(disponibles),
        reason=razon,
        per_measurement=por_medida,
        confidence=confianza,
    )
