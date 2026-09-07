"""Analisis corporal (Fase 3).

Punto unico donde se elige la implementacion, igual que `app/ai/`. Cuando
entre MediaPipe, cumple `BodyAnalysisProvider` y solo cambia una rama de
`get_body_analysis_provider()`.
"""

from app.core.config import settings
from app.vision.analysis_provider import (
    BodyAnalysisError,
    BodyAnalysisProvider,
    BodyMeasurements,
)
from app.vision.mock_analysis import MockBodyAnalysisProvider

__all__ = [
    "BodyAnalysisProvider",
    "BodyAnalysisError",
    "BodyMeasurements",
    "MockBodyAnalysisProvider",
    "get_body_analysis_provider",
]


def get_body_analysis_provider() -> BodyAnalysisProvider:
    """Devuelve el analizador configurado en `BODY_ANALYSIS_PROVIDER`.

    Un valor desconocido falla en vez de caer en silencio al simulado:
    creer que unas medidas salieron de vision por computador cuando son una
    proporcion inventada seria enganoso.
    """
    nombre = settings.BODY_ANALYSIS_PROVIDER.strip().lower()

    if nombre in ("mock", "mock-analysis"):
        return MockBodyAnalysisProvider()

    raise ValueError(
        f"BODY_ANALYSIS_PROVIDER={settings.BODY_ANALYSIS_PROVIDER!r} no corresponde "
        "a ningun analizador. Valores admitidos: 'mock'."
    )
