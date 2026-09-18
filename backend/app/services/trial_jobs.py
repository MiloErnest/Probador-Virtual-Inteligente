"""Procesado de pruebas fuera del ciclo de la petición.

POR QUÉ ABRE SU PROPIA SESIÓN
-----------------------------
La tarea corre DESPUÉS de que la respuesta HTTP se haya enviado, y para
entonces la sesión de base de datos de esa petición ya está cerrada. Usarla
daría un error de sesión cerrada la primera vez que se guarde el resultado.

POR QUÉ `BackgroundTasks` Y NO UNA COLA
---------------------------------------
Regla 11 del proyecto: nada de infraestructura por si acaso. Una cola son tres
piezas más —intermediario, trabajador, supervisión— para un problema que hoy no
existe: un proceso y unos pocos usuarios.

Su límite está asumido y anotado: si el proceso se para mientras una prueba
está en `processing`, esa prueba se queda ahí para siempre. No hay reintentos.
Con el motor determinista son 500 ms de ventana; con el generativo son treinta
segundos, que ya es una ventana real — pero `status` está modelado desde el
principio, así que meter una cola el día que haga falta no obliga a rehacer la
tabla.
"""

import logging

from app.core.database import SessionLocal
from app.repositories.fabric import FabricRepository
from app.repositories.fabric_trial import FabricTrialRepository
from app.repositories.garment_upload import GarmentUploadRepository
from app.services.fabric_trial import FabricTrialService
from app.services.storage import get_storage

logger = logging.getLogger("app.trials")


def run_trial_job(trial_id: int) -> None:
    """Procesa una prueba. Nunca lanza: es el final de la cadena."""
    try:
        with SessionLocal() as session:
            servicio = FabricTrialService(
                FabricTrialRepository(session),
                GarmentUploadRepository(session),
                FabricRepository(session),
                get_storage(),
            )
            servicio.process(trial_id)
    except Exception:  # noqa: BLE001
        # Si esto explota, nadie lo recoge: no hay nadie esperando la
        # excepción. Sin el registro, la prueba se quedaría en `processing`
        # para siempre y no habría ni rastro de por qué.
        logger.exception("Falló el procesado de la prueba %s", trial_id)
