"""Reglas de negocio de sesiones de prueba virtual.

CICLO DE VIDA DE UNA PRUEBA
---------------------------
    pending -> processing -> completed
                          -> failed

`create()` corre dentro de la petición HTTP y termina rápido: valida, guarda
la foto y deja la fila en `pending`. `process()` corre DESPUÉS, en una tarea
de fondo, porque llamar a un modelo de try-on tarda de segundos a minutos y
ninguna petición HTTP debe quedarse esperando eso.

Se usa `BackgroundTasks` de FastAPI y no Celery (regla 10: nada de
infraestructura por adelantado). Su limitación es real y está anotada: si el
proceso se reinicia mientras una prueba está en `processing`, esa prueba se
queda ahí para siempre. Con un solo proceso y un usuario, es asumible; el día
que deje de serlo, `status` ya está modelado y la cola encaja sin rehacer la
tabla.
"""

import logging

from app.ai.provider import TryOnProvider, TryOnProviderError
from app.models.try_on_session import TryOnSession, TryOnStatus
from app.models.design import DesignStatus
from app.repositories.design import DesignRepository
from app.repositories.garment import GarmentRepository
from app.repositories.try_on_session import TryOnSessionRepository
from app.schemas.try_on_session import TryOnSessionRead
from app.services.exceptions import NotFoundError, ValidationError
from app.services.images import validate_image
from app.services.storage import FOLDER_RESULTS, FOLDER_UPLOADS, Storage

logger = logging.getLogger("app.try_on")


class TryOnSessionService:
    def __init__(
        self,
        repository: TryOnSessionRepository,
        garments: GarmentRepository,
        designs: DesignRepository,
        storage: Storage,
    ) -> None:
        self.repository = repository
        # Necesita leer prendas para validar y para recuperar su imagen. Se
        # inyecta el repositorio y no `GarmentService` porque aqui hace falta
        # el modelo con su `image_key`, no el contrato publico que expone
        # `image_url`.
        self.garments = garments
        # Fase 2: una prueba tambien puede partir de un diseno generado.
        self.designs = designs
        self.storage = storage

    # --- Consultas ---

    def list_by_user(
        self, user_id: int, *, limit: int = 50, offset: int = 0
    ) -> list[TryOnSessionRead]:
        sessions = self.repository.list_by_user(user_id, limit=limit, offset=offset)
        return [self.to_read(session) for session in sessions]

    def get_for_user(self, session_id: int, *, user_id: int) -> TryOnSessionRead:
        """Devuelve una prueba solo si pertenece a ese usuario.

        Una prueba ajena produce el mismo `NotFoundError` que una inexistente,
        y con el mismo mensaje. Es deliberado: si el error distinguiera ambos
        casos, recorrer identificadores permitiría contar cuántas pruebas hay
        en el sistema y quién las tiene.

        La comprobación vive aquí y no en la ruta porque "de quién es este
        recurso" es una regla de negocio. La ruta solo traduce el error a un
        404.
        """
        return self.to_read(self._get_owned(session_id, user_id=user_id))

    # --- Comandos ---

    def create(
        self,
        *,
        user_id: int,
        photo: bytes,
        max_bytes: int,
        garment_id: int | None = None,
        design_id: int | None = None,
    ) -> TryOnSessionRead:
        """Registra una prueba nueva y deja la foto guardada.

        No llama al proveedor: eso es trabajo de `process()`. Aquí solo se
        valida y se persiste, para que la respuesta HTTP sea inmediata.
        """
        # La prenda viene del catálogo o de un diseño propio, nunca de las
        # dos ni de ninguna. La base impone la misma regla con una CHECK;
        # esto es para dar un mensaje entendible antes de llegar a ella.
        if (garment_id is None) == (design_id is None):
            raise ValidationError(
                "Indica una prenda del catálogo o un diseño tuyo, pero no ambos."
            )

        if garment_id is not None:
            self._validar_prenda(garment_id)
        else:
            self._validar_diseno(design_id, user_id=user_id)

        # Valida abriendo el archivo, no fiándose de la cabecera del cliente.
        extension = validate_image(photo, max_bytes=max_bytes)

        input_key = self.storage.save(photo, folder=FOLDER_UPLOADS, extension=extension)

        session = self.repository.create(
            user_id=user_id,
            garment_id=garment_id,
            design_id=design_id,
            input_image_key=input_key,
        )
        return self.to_read(session)

    def _validar_prenda(self, garment_id: int) -> None:
        garment = self.garments.get_by_id(garment_id)
        if garment is None:
            raise NotFoundError(f"No existe la prenda {garment_id}.")
        if not garment.active:
            raise ValidationError(
                f"La prenda «{garment.name}» está retirada del catálogo."
            )
        if not garment.image_key:
            raise ValidationError(
                f"La prenda «{garment.name}» todavía no tiene imagen, "
                "así que no se puede probar."
            )

    def _validar_diseno(self, design_id: int, *, user_id: int) -> None:
        design = self.designs.get_by_id(design_id)
        # Un diseño ajeno responde como inexistente: probarse el diseño de
        # otro sería una fuga, y un 403 confirmaría que existe.
        if design is None or design.user_id != user_id:
            raise NotFoundError(f"No existe el diseño {design_id}.")
        if design.status is not DesignStatus.COMPLETED or not design.image_key:
            raise ValidationError(
                "Ese diseño todavía no se ha generado, así que no se puede probar."
            )

    def process(self, session_id: int, *, provider: TryOnProvider) -> None:
        """Genera el resultado de una prueba. Se ejecuta en segundo plano.

        No propaga excepciones: nadie está escuchando. Cualquier fallo se
        guarda en la propia fila (`status=failed` y `error_message`), que es
        donde el usuario puede verlo. Una excepción que se pierde en una tarea
        de fondo dejaría la prueba clavada en `processing` sin explicación.
        """
        session = self.repository.get_by_id(session_id)
        if session is None:
            logger.warning("La prueba %s ya no existe; se descarta.", session_id)
            return

        # Defensa ante un doble encolado: si ya no está pendiente, otra
        # ejecución se está ocupando o ya terminó.
        if session.status is not TryOnStatus.PENDING:
            logger.info(
                "La prueba %s está en %s, no en pending; no se reprocesa.",
                session_id,
                session.status.value,
            )
            return

        session.status = TryOnStatus.PROCESSING
        session.provider = provider.name
        self.repository.save(session)

        try:
            person = self.storage.read(session.input_image_key)
            # `source_image_key` resuelve el origen (prenda o diseño) para
            # que este código no tenga que preguntarlo.
            garment_key = session.source_image_key
            if not garment_key:
                raise TryOnProviderError(
                    "La prenda o el diseño ya no tienen imagen disponible."
                )
            garment = self.storage.read(garment_key)

            result = provider.generate(person=person, garment=garment)

            session.output_image_key = self.storage.save(
                result, folder=FOLDER_RESULTS, extension=".png"
            )
            session.status = TryOnStatus.COMPLETED
            session.error_message = None
            logger.info("Prueba %s completada con %s.", session_id, provider.name)

        except TryOnProviderError as exc:
            # Error previsto del proveedor: su mensaje ya es presentable.
            session.status = TryOnStatus.FAILED
            session.error_message = str(exc)
            logger.warning("Prueba %s fallida: %s", session_id, exc)

        except FileNotFoundError:
            session.status = TryOnStatus.FAILED
            session.error_message = "No se encontró alguna de las imágenes de entrada."
            logger.exception("Prueba %s: falta un archivo en el almacén.", session_id)

        except Exception:  # noqa: BLE001 - la tarea de fondo no puede dejar escapar nada
            session.status = TryOnStatus.FAILED
            # Mensaje genérico a propósito: el detalle va al log del servidor,
            # no a la pantalla del usuario.
            session.error_message = (
                "Error inesperado al generar el resultado. Inténtalo de nuevo."
            )
            logger.exception("Prueba %s: error inesperado.", session_id)

        self.repository.save(session)

    # --- Interno y traducción ---

    def _get_owned(self, session_id: int, *, user_id: int) -> TryOnSession:
        session = self.repository.get_by_id(session_id)
        if session is None or session.user_id != user_id:
            raise NotFoundError(f"No existe la sesión de prueba {session_id}.")
        return session

    def to_read(self, session: TryOnSession) -> TryOnSessionRead:
        return TryOnSessionRead(
            id=session.id,
            user_id=session.user_id,
            garment_id=session.garment_id,
            design_id=session.design_id,
            status=session.status,
            input_image_url=self.storage.public_url(session.input_image_key),
            output_image_url=self.storage.public_url(session.output_image_key),
            error_message=session.error_message,
            provider=session.provider,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
