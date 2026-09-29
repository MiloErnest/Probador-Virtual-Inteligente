"""Reglas de negocio del probador: fotos de persona y pruebas sobre ellas.

NO DUPLICA EL TALLER
--------------------
La prenda no se sube aquí: sale del taller, que ya sabe subirla, recortarla y
vestirla con tela. Este servicio solo añade lo que el taller no tiene —la foto
de la persona— y junta las dos cosas. Una prenda nueva se sube por el mismo
`POST /garment-uploads` de siempre.

EL CICLO ES EL DE LAS PRUEBAS DE TELA
-------------------------------------
Crear responde 202 con la prueba en `pending`, se procesa en segundo plano y
el cliente sondea. Con un modelo que tarda medio minuto no hay otra forma, y
es el contrato que la interfaz ya sabe manejar.
"""

from __future__ import annotations

import io
import time

from PIL import Image, ImageOps

from app.core.config import settings
from app.models.fabric_trial import TrialStatus
from app.models.garment_upload import GarmentKind
from app.models.person_photo import PersonPhoto
from app.models.try_on import TryOn
from app.repositories.fabric_trial import FabricTrialRepository
from app.repositories.garment_upload import GarmentUploadRepository
from app.repositories.person_photo import PersonPhotoRepository
from app.repositories.try_on import TryOnRepository
from app.schemas.try_on import PersonPhotoRead, TryOnCreate, TryOnRead
from app.services.exceptions import NotFoundError, ValidationError
from app.services.images import validate_image
from app.services.storage import FOLDER_PEOPLE, FOLDER_TRY_ONS, Storage
from app.textil import ErrorDeMotor


class PersonPhotoService:
    def __init__(
        self, repository: PersonPhotoRepository, try_ons: TryOnRepository, storage: Storage
    ) -> None:
        self.repository = repository
        self.try_ons = try_ons
        self.storage = storage

    def list(self, user_id: int) -> list[PersonPhotoRead]:
        return [self.to_read(f) for f in self.repository.list_for_user(user_id)]

    def create(self, *, user_id: int, content: bytes, max_bytes: int) -> PersonPhotoRead:
        validate_image(content, max_bytes=max_bytes)
        try:
            imagen = Image.open(io.BytesIO(content))
            imagen.load()
        except Exception as exc:  # noqa: BLE001
            raise ValidationError("No se ha podido abrir la imagen.") from exc

        # LA FOTO SE GUARDA LIMPIA
        # Primero se endereza: un móvil guarda la foto de lado y apunta el giro
        # en los metadatos. El navegador lo respeta y el servidor no, así que
        # sin esto el modelo recibiría a la persona tumbada. Después se vuelve
        # a codificar, y con eso se quedan fuera todos los metadatos: la
        # ubicación GPS, el teléfono, la fecha.
        imagen = ImageOps.exif_transpose(imagen).convert("RGB")
        imagen.thumbnail(
            (settings.PERSON_PHOTO_MAX_SIDE, settings.PERSON_PHOTO_MAX_SIDE),
            Image.Resampling.LANCZOS,
        )
        buffer = io.BytesIO()
        imagen.save(buffer, format="JPEG", quality=92, optimize=True)

        foto = self.repository.create(
            user_id=user_id,
            image_key=self.storage.save(buffer.getvalue(), folder=FOLDER_PEOPLE, extension=".jpg"),
            width=imagen.width,
            height=imagen.height,
        )
        return self.to_read(foto)

    def delete(self, photo_id: int, user_id: int) -> None:
        """Borra la foto Y todas las pruebas hechas con ella.

        Una prueba sobre persona es esa persona con otra ropa: si alguien
        retira su foto, quedarse con los resultados sería quedarse con ella.
        La base borra las filas en cascada; los archivos se borran aquí.
        """
        foto = self.repository.get_for_user(photo_id, user_id)
        if foto is None:
            raise NotFoundError(f"No existe la foto {photo_id}.")
        claves = [foto.image_key]
        for prueba in self.try_ons.list_for_photo(foto.id):
            claves += [prueba.output_image_key, prueba.garment_image_key]
        self.repository.delete(foto)
        for clave in claves:
            if clave:
                self.storage.delete(clave)

    def to_read(self, foto: PersonPhoto) -> PersonPhotoRead:
        return PersonPhotoRead(
            id=foto.id,
            user_id=foto.user_id,
            image_url=self.storage.public_url(foto.image_key),
            width=foto.width,
            height=foto.height,
            created_at=foto.created_at,
            updated_at=foto.updated_at,
        )


class TryOnService:
    def __init__(
        self,
        repository: TryOnRepository,
        photos: PersonPhotoRepository,
        trials: FabricTrialRepository,
        uploads: GarmentUploadRepository,
        storage: Storage,
    ) -> None:
        self.repository = repository
        self.photos = photos
        self.trials = trials
        self.uploads = uploads
        self.storage = storage

    # --- Consultas ---

    def list(
        self, user_id: int, *, person_photo_id: int | None = None, limit: int = 60, offset: int = 0
    ) -> list[TryOnRead]:
        pruebas = self.repository.list_for_user(
            user_id, person_photo_id=person_photo_id, limit=limit, offset=offset
        )
        return [self.to_read(p) for p in pruebas]

    def get(self, try_on_id: int, user_id: int) -> TryOnRead:
        return self.to_read(self._get_or_fail(try_on_id, user_id))

    # --- Comandos ---

    def create(self, user_id: int, data: TryOnCreate) -> TryOnRead:
        if self.photos.get_for_user(data.person_photo_id, user_id) is None:
            raise NotFoundError(f"No existe la foto {data.person_photo_id}.")

        if data.fabric_trial_id is not None:
            prueba = self.trials.get_for_user(data.fabric_trial_id, user_id)
            if prueba is None:
                raise NotFoundError(f"No existe la prueba de tela {data.fabric_trial_id}.")
            if prueba.status is not TrialStatus.COMPLETED or not prueba.output_image_key:
                raise ValidationError(
                    "Esa prueba de tela todavía no tiene imagen: espera a que termine."
                )
        else:
            prenda = self.uploads.get_for_user(data.garment_upload_id, user_id)
            if prenda is None:
                raise NotFoundError(f"No existe la prenda {data.garment_upload_id}.")
            if prenda.mask_key is None:
                raise ValidationError("Esa prenda no tiene recorte; vuelve a subirla.")

        return self.to_read(
            self.repository.create(
                user_id=user_id,
                person_photo_id=data.person_photo_id,
                fabric_trial_id=data.fabric_trial_id,
                garment_upload_id=data.garment_upload_id,
                category=data.category,
                status=TrialStatus.PENDING,
            )
        )

    def delete(self, try_on_id: int, user_id: int) -> None:
        prueba = self._get_or_fail(try_on_id, user_id)
        claves = [prueba.output_image_key, prueba.garment_image_key]
        self.repository.delete(prueba)
        for clave in claves:
            if clave:
                self.storage.delete(clave)

    # --- Procesado en segundo plano ---

    def process(self, try_on_id: int) -> None:
        from app.probador import recortar_prenda, vestir_persona

        prueba = self.repository.get_by_id(try_on_id)
        if prueba is None or prueba.status is not TrialStatus.PENDING:
            # Ya procesada, o borrada mientras esperaba: repetirla gastaría
            # cuota del modelo por nada.
            return

        prueba.status = TrialStatus.PROCESSING
        self.repository.save(prueba)
        comenzado = time.perf_counter()
        try:
            persona, prenda, es_boceto = self._cargar(prueba)
            recorte = recortar_prenda(*prenda)
            buffer = io.BytesIO()
            recorte.save(buffer, format="PNG", optimize=True)
            prueba.garment_image_key = self.storage.save(
                buffer.getvalue(), folder=FOLDER_TRY_ONS, extension=".png"
            )
            self.repository.save(prueba)

            vestida = vestir_persona(
                persona,
                recorte,
                prueba.category,
                variante=prueba.id,
            )
        except (ErrorDeMotor, ValidationError) as exc:
            prueba.status = TrialStatus.FAILED
            prueba.error_message = str(exc)
        except Exception as exc:  # noqa: BLE001
            prueba.status = TrialStatus.FAILED
            prueba.error_message = f"Error inesperado del probador ({type(exc).__name__})."
        else:
            buffer = io.BytesIO()
            vestida.imagen.save(buffer, format="JPEG", quality=92, optimize=True)
            prueba.status = TrialStatus.COMPLETED
            prueba.output_image_key = self.storage.save(
                buffer.getvalue(), folder=FOLDER_TRY_ONS, extension=".jpg"
            )
            prueba.provider = vestida.proveedor
            prueba.edited_fraction = round(vestida.editado, 4)
            avisos = [vestida.aviso] if vestida.aviso else []
            if es_boceto:
                avisos.append(
                    "La prenda es un boceto: el modelo la interpreta como una foto de "
                    "producto, así que el resultado depende de lo realista que sea el dibujo."
                )
            prueba.notice = " ".join(avisos) or None

        prueba.duration_ms = int((time.perf_counter() - comenzado) * 1000)
        self.repository.save(prueba)

    def _cargar(self, prueba: TryOn) -> tuple[Image.Image, tuple[Image.Image, Image.Image], bool]:
        """La foto de la persona, y la prenda con su máscara."""
        foto = self.photos.get_by_id(prueba.person_photo_id)
        if foto is None:
            raise ValidationError("La foto de la persona ya no existe.")
        persona = self._abrir(foto.image_key)

        if prueba.fabric_trial_id is not None:
            tela = self.trials.get_by_id(prueba.fabric_trial_id)
            if tela is None or not tela.output_image_key:
                raise ValidationError("La prueba de tela ya no existe.")
            subida = self.uploads.get_by_id(tela.garment_upload_id)
            # La imagen YA generada de la prueba de tela: no se vuelve a vestir.
            imagen_prenda = self._abrir(tela.output_image_key)
        else:
            subida = self.uploads.get_by_id(prueba.garment_upload_id)
            imagen_prenda = self._abrir(subida.image_key) if subida else None

        if subida is None or subida.mask_key is None or imagen_prenda is None:
            raise ValidationError("La prenda ya no existe o no tiene recorte.")
        mascara = self._abrir(subida.mask_key)
        return persona, (imagen_prenda, mascara), subida.kind is GarmentKind.SKETCH

    def _abrir(self, clave: str) -> Image.Image:
        imagen = Image.open(io.BytesIO(self.storage.read(clave)))
        imagen.load()
        return imagen

    # --- Traducción ---

    def to_read(self, prueba: TryOn) -> TryOnRead:
        foto = self.photos.get_by_id(prueba.person_photo_id)
        return TryOnRead(
            id=prueba.id,
            user_id=prueba.user_id,
            person_photo_id=prueba.person_photo_id,
            fabric_trial_id=prueba.fabric_trial_id,
            garment_upload_id=prueba.garment_upload_id,
            category=prueba.category,
            status=prueba.status,
            person_image_url=self.storage.public_url(foto.image_key) if foto else None,
            garment_image_url=self.storage.public_url(prueba.garment_image_key),
            output_image_url=self.storage.public_url(prueba.output_image_key),
            error_message=prueba.error_message,
            notice=prueba.notice,
            provider=prueba.provider,
            duration_ms=prueba.duration_ms,
            edited_fraction=prueba.edited_fraction,
            created_at=prueba.created_at,
            updated_at=prueba.updated_at,
        )

    def _get_or_fail(self, try_on_id: int, user_id: int) -> TryOn:
        prueba = self.repository.get_for_user(try_on_id, user_id)
        if prueba is None:
            raise NotFoundError(f"No existe la prueba {try_on_id}.")
        return prueba
