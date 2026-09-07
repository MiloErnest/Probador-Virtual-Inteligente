"""Reglas de negocio del perfil corporal y la recomendación de talla (Fase 3).

A DIFERENCIA DE LAS PRUEBAS Y LOS DISEÑOS, ESTO ES SÍNCRONO
-----------------------------------------------------------
No hay tarea de fondo. El análisis de una foto tarda del orden de un segundo,
no minutos, y el usuario está esperando la respuesta delante de la pantalla.
Encolarlo obligaría a sondear para nada y añadiría estados que no aportan.

Si algún día el proveedor real resulta ser lento, se mueve a `BackgroundTasks`
igual que los otros dos: el patrón ya está en el proyecto.
"""

import logging

from app.models.body_profile import BodyProfile, MeasurementSource
from app.models.garment import GarmentCategory
from app.repositories.body_profile import BodyProfileRepository
from app.repositories.garment import GarmentRepository
from app.schemas.body_profile import BodyProfileRead, BodyProfileUpdate, SizeRecommendationRead
from app.services.exceptions import NotFoundError, ValidationError
from app.services.images import validate_image
from app.services.sizing import recommend
from app.services.storage import FOLDER_BODY, Storage
from app.vision.analysis_provider import BodyAnalysisError, BodyAnalysisProvider

logger = logging.getLogger("app.body")


class BodyProfileService:
    def __init__(
        self,
        repository: BodyProfileRepository,
        garments: GarmentRepository,
        storage: Storage,
    ) -> None:
        self.repository = repository
        self.garments = garments
        self.storage = storage

    # --- Consultas ---

    def get(self, user_id: int) -> BodyProfileRead:
        perfil = self.repository.get_by_user(user_id)
        if perfil is None:
            raise NotFoundError("Todavía no has creado tu perfil corporal.")
        return self.to_read(perfil)

    def recommend_size(self, user_id: int, garment_id: int) -> SizeRecommendationRead:
        perfil = self.repository.get_by_user(user_id)
        if perfil is None:
            raise NotFoundError(
                "Necesitas un perfil corporal para calcular tu talla."
            )

        prenda = self.garments.get_by_id(garment_id)
        if prenda is None:
            raise NotFoundError(f"No existe la prenda {garment_id}.")

        return self._to_recommendation(recommend(perfil, prenda.category), prenda.category)

    def recommend_size_for_category(
        self, user_id: int, category: GarmentCategory
    ) -> SizeRecommendationRead:
        """Talla para una categoría suelta, sin una prenda concreta.

        Útil para los diseños generados, que no pertenecen al catálogo y por
        tanto no tienen categoría propia: la elige el usuario.
        """
        perfil = self.repository.get_by_user(user_id)
        if perfil is None:
            raise NotFoundError(
                "Necesitas un perfil corporal para calcular tu talla."
            )
        return self._to_recommendation(recommend(perfil, category), category)

    # --- Comandos ---

    def upsert(self, user_id: int, data: BodyProfileUpdate) -> BodyProfileRead:
        """Crea el perfil o actualiza el existente.

        Es un upsert y no un create+update separados porque el usuario tiene
        un perfil y solo uno: obligarle a saber si ya existe sería trasladarle
        un detalle nuestro.

        Solo se tocan los campos que llegan. Enviar `{"height_cm": 170}` no
        debe borrar el resto de medidas.
        """
        cambios = data.model_dump(exclude_unset=True)
        if not cambios:
            raise ValidationError("No has indicado ninguna medida.")

        perfil = self.repository.get_by_user(user_id)
        if perfil is None:
            perfil = self.repository.create(user_id=user_id)

        for campo, valor in cambios.items():
            setattr(perfil, campo, valor)

        # Lo ha escrito una persona: pasa a contar como medida manual, que es
        # más fiable que una estimación por foto.
        perfil.source = MeasurementSource.MANUAL

        return self.to_read(self.repository.save(perfil))

    def analyse_photo(
        self,
        user_id: int,
        *,
        photo: bytes,
        max_bytes: int,
        provider: BodyAnalysisProvider,
        height_cm: float | None = None,
    ) -> BodyProfileRead:
        """Estima las medidas desde una fotografía y las guarda en el perfil."""
        validate_image(photo, max_bytes=max_bytes)

        perfil = self.repository.get_by_user(user_id)
        # La altura conocida es la referencia que convierte proporciones en
        # centímetros. Si el usuario no la manda ahora, se usa la que ya
        # tuviera guardada antes de caer en la altura supuesta.
        altura = height_cm if height_cm is not None else (perfil.height_cm if perfil else None)

        try:
            medidas = provider.analyse(photo=photo, height_cm=altura)
        except BodyAnalysisError as exc:
            raise ValidationError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("Fallo inesperado analizando la fotografía.")
            raise ValidationError(
                "No se pudo analizar la fotografía. Inténtalo con otra."
            ) from exc

        if perfil is None:
            perfil = self.repository.create(user_id=user_id)

        clave_anterior = perfil.photo_key
        perfil.photo_key = self.storage.save(photo, folder=FOLDER_BODY, extension=".png")

        for campo in ("height_cm", "chest_cm", "waist_cm", "hips_cm", "inseam_cm"):
            valor = getattr(medidas, campo)
            if valor is not None:
                setattr(perfil, campo, valor)

        perfil.source = MeasurementSource.ANALYSIS
        perfil = self.repository.save(perfil)

        # La foto anterior se borra DESPUÉS de guardar la nueva: si la
        # escritura en base de datos fallara, no queremos haber destruido la
        # única imagen que había.
        if clave_anterior:
            self.storage.delete(clave_anterior)

        return self.to_read(perfil, confidence=medidas.confidence)

    def delete(self, user_id: int) -> None:
        """Borra el perfil y la fotografía asociada.

        Son datos del cuerpo de una persona: tiene que poder retirarlos, y el
        archivo debe irse con la fila, no quedarse huérfano en el disco.
        """
        perfil = self.repository.get_by_user(user_id)
        if perfil is None:
            raise NotFoundError("No tienes perfil corporal que borrar.")

        clave = perfil.photo_key
        self.repository.delete(perfil)
        if clave:
            self.storage.delete(clave)

    # --- Traducción ---

    def to_read(self, perfil: BodyProfile, *, confidence: float | None = None) -> BodyProfileRead:
        return BodyProfileRead(
            user_id=perfil.user_id,
            height_cm=perfil.height_cm,
            weight_kg=perfil.weight_kg,
            chest_cm=perfil.chest_cm,
            waist_cm=perfil.waist_cm,
            hips_cm=perfil.hips_cm,
            inseam_cm=perfil.inseam_cm,
            source=perfil.source,
            photo_url=self.storage.public_url(perfil.photo_key),
            analysis_confidence=confidence,
            created_at=perfil.created_at,
            updated_at=perfil.updated_at,
        )

    def _to_recommendation(self, resultado, category: GarmentCategory) -> SizeRecommendationRead:
        return SizeRecommendationRead(
            size=resultado.size,
            category=category,
            based_on=resultado.based_on,
            reason=resultado.reason,
            per_measurement=resultado.per_measurement,
            confidence=resultado.confidence,
        )
