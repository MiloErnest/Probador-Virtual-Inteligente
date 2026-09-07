"""Reglas de negocio de los diseños generados por texto (Fase 2).

Mismo patrón que las pruebas virtuales, y a propósito: `create()` valida y
persiste dentro de la petición HTTP; `process()` genera la imagen después, en
una tarea de fondo. Repetir la forma en vez de inventar una nueva hace que
quien entienda un flujo entienda el otro.
"""

import logging

from app.ai.design_provider import DesignProvider, DesignProviderError
from app.models.design import Design, DesignStatus
from app.repositories.design import DesignRepository
from app.schemas.design import DesignRead
from app.services.exceptions import NotFoundError, ValidationError
from app.services.storage import FOLDER_DESIGNS, Storage

logger = logging.getLogger("app.design")



class DesignService:
    def __init__(self, repository: DesignRepository, storage: Storage) -> None:
        self.repository = repository
        self.storage = storage

    # --- Consultas ---

    def list_by_user(self, user_id: int, *, limit: int = 50, offset: int = 0) -> list[DesignRead]:
        return [
            self.to_read(d)
            for d in self.repository.list_by_user(user_id, limit=limit, offset=offset)
        ]

    def get_for_user(self, design_id: int, *, user_id: int) -> DesignRead:
        return self.to_read(self._get_owned(design_id, user_id=user_id))

    # --- Comandos ---

    def create(self, *, user_id: int, prompt: str) -> DesignRead:
        """Registra un diseño nuevo, todavía sin imagen."""
        texto = prompt.strip()
        if not texto:
            raise ValidationError("La descripción no puede estar vacía.")

        return self.to_read(self.repository.create(user_id=user_id, prompt=texto))

    def refine(self, design_id: int, *, user_id: int, refinement: str) -> DesignRead:
        """Crea una iteración a partir de un diseño existente.

        NO sobrescribe al padre: crea un diseño nuevo que lo referencia. Así
        nunca se pierde una versión que gustaba más, y queda el rastro de cómo
        se llegó al resultado.
        """
        padre = self._get_owned(design_id, user_id=user_id)

        if padre.status is not DesignStatus.COMPLETED:
            raise ValidationError(
                "Solo se puede iterar sobre un diseño que ya se haya generado."
            )

        texto = refinement.strip()
        if not texto:
            raise ValidationError("La instrucción no puede estar vacía.")

        return self.to_read(
            self.repository.create(
                user_id=user_id,
                # El texto original se hereda: el usuario solo escribe el
                # cambio, no toda la descripción otra vez.
                prompt=padre.prompt,
                parent_id=padre.id,
                refinement=texto,
            )
        )

    def process(self, design_id: int, *, provider: DesignProvider) -> None:
        """Genera la imagen de un diseño. Se ejecuta en segundo plano.

        No propaga excepciones, por el mismo motivo que en las pruebas
        virtuales: nadie las recogería y el diseño se quedaría clavado en
        `processing` sin explicación.
        """
        design = self.repository.get_by_id(design_id)
        if design is None:
            logger.warning("El diseño %s ya no existe; se descarta.", design_id)
            return

        if design.status is not DesignStatus.PENDING:
            logger.info("El diseño %s no está pendiente; no se reprocesa.", design_id)
            return

        design.status = DesignStatus.PROCESSING
        design.provider = provider.name
        self.repository.save(design)

        try:
            # Al iterar se le pasa la imagen del padre para que el proveedor
            # pueda partir de ella. Si el padre perdió su imagen, se degrada a
            # una generación desde cero en vez de fallar.
            base = None
            if design.parent is not None and design.parent.image_key:
                try:
                    base = self.storage.read(design.parent.image_key)
                except FileNotFoundError:
                    logger.warning(
                        "El diseño padre %s no tiene su archivo; se genera desde cero.",
                        design.parent_id,
                    )

            imagen = provider.generate(
                prompt=design.prompt,
                base_image=base,
                refinement=design.refinement,
            )

            design.image_key = self.storage.save(
                imagen, folder=FOLDER_DESIGNS, extension=".png"
            )
            design.status = DesignStatus.COMPLETED
            design.error_message = None
            logger.info("Diseño %s completado con %s.", design_id, provider.name)

        except DesignProviderError as exc:
            design.status = DesignStatus.FAILED
            design.error_message = str(exc)
            logger.warning("Diseño %s fallido: %s", design_id, exc)

        except Exception:  # noqa: BLE001 - la tarea de fondo no deja escapar nada
            design.status = DesignStatus.FAILED
            design.error_message = (
                "Error inesperado al generar el diseño. Inténtalo de nuevo."
            )
            logger.exception("Diseño %s: error inesperado.", design_id)

        self.repository.save(design)

    # --- Interno y traducción ---

    def _get_owned(self, design_id: int, *, user_id: int) -> Design:
        design = self.repository.get_by_id(design_id)
        # Un diseño ajeno responde igual que uno inexistente, por el mismo
        # motivo que en el resto del proyecto: un 403 confirmaría que existe.
        if design is None or design.user_id != user_id:
            raise NotFoundError(f"No existe el diseño {design_id}.")
        return design

    def to_read(self, design: Design) -> DesignRead:
        return DesignRead(
            id=design.id,
            user_id=design.user_id,
            prompt=design.prompt,
            refinement=design.refinement,
            parent_id=design.parent_id,
            status=design.status,
            image_url=self.storage.public_url(design.image_key),
            error_message=design.error_message,
            provider=design.provider,
            created_at=design.created_at,
            updated_at=design.updated_at,
        )
