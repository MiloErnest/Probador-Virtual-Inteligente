"""Ejecución en segundo plano de las pruebas virtuales.

POR QUÉ ESTE MÓDULO EXISTE
--------------------------
La tarea de fondo corre **después** de que la respuesta HTTP se haya enviado,
y para entonces la sesión de base de datos de esa petición ya está cerrada:
`get_session` la cierra al salir del `with`. Usarla desde aquí daría un error
de sesión cerrada, o peor, funcionaría a ratos.

Por eso la tarea abre su propia sesión, la usa y la cierra. Es un ciclo de
vida distinto al de una petición y merece su propia función, en vez de
esconderlo dentro de la ruta.
"""

import logging

from app.ai import get_design_provider, get_try_on_provider
from app.core.database import SessionLocal
from app.repositories.design import DesignRepository
from app.repositories.garment import GarmentRepository
from app.repositories.try_on_session import TryOnSessionRepository
from app.services.design import DesignService
from app.services.storage import get_storage
from app.services.try_on_session import TryOnSessionService

logger = logging.getLogger("app.try_on")


def run_try_on_job(session_id: int) -> None:
    """Procesa una prueba. Pensada para `BackgroundTasks.add_task`.

    No lanza excepciones nunca. Una excepción aquí no la recoge nadie: se
    perdería en el registro del servidor y la prueba se quedaría clavada en
    `processing` sin que el usuario supiera por qué. `process()` ya guarda los
    fallos en la propia fila; este `try` cubre lo que pueda romperse antes de
    llegar a él, como una configuración de `AI_PROVIDER` inválida.
    """
    try:
        with SessionLocal() as db:
            service = TryOnSessionService(
                TryOnSessionRepository(db),
                GarmentRepository(db),
                DesignRepository(db),
                get_storage(),
            )
            service.process(session_id, provider=get_try_on_provider())
    except Exception:  # noqa: BLE001
        logger.exception(
            "No se pudo siquiera arrancar el procesado de la prueba %s. "
            "Revisa AI_PROVIDER y la conexión a la base de datos.",
            session_id,
        )


def run_design_job(design_id: int) -> None:
    """Genera la imagen de un diseño. Pensada para `BackgroundTasks.add_task`.

    Mismas razones que `run_try_on_job`: sesión propia porque la de la
    petición ya está cerrada, y nada de excepciones hacia fuera.
    """
    try:
        with SessionLocal() as db:
            service = DesignService(DesignRepository(db), get_storage())
            service.process(design_id, provider=get_design_provider())
    except Exception:  # noqa: BLE001
        logger.exception(
            "No se pudo arrancar la generación del diseño %s. "
            "Revisa DESIGN_PROVIDER y la conexión a la base de datos.",
            design_id,
        )
