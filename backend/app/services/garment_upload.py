"""Reglas de negocio de las prendas que sube el usuario.

EL RECORTE SE HACE AL SUBIR, NO AL PROBAR
-----------------------------------------
Cuesta unos doscientos milisegundos y se necesita idéntico para cada tela. Si
se hiciera al probar, probar diez telas serían diez recortes iguales; haciéndolo
una vez, son diez multiplicaciones. Además permite avisar de un recorte malo
ANTES de que el usuario empiece a gastar pruebas sobre él.
"""

import io

from PIL import Image

from app.models.garment_upload import GarmentKind, GarmentUpload
from app.repositories.garment_upload import GarmentUploadRepository
from app.schemas.garment_upload import GarmentUploadRead
from app.services.exceptions import NotFoundError, ValidationError
from app.services.images import validate_image
from app.services.storage import FOLDER_MASKS, FOLDER_UPLOADS, Storage
from app.textil import segmentar_prenda


class GarmentUploadService:
    def __init__(self, repository: GarmentUploadRepository, storage: Storage) -> None:
        self.repository = repository
        self.storage = storage

    def list(self, user_id: int, *, limit: int = 60, offset: int = 0) -> list[GarmentUploadRead]:
        return [self.to_read(u) for u in self.repository.list_for_user(user_id, limit=limit, offset=offset)]

    def get(self, upload_id: int, user_id: int) -> GarmentUploadRead:
        return self.to_read(self._get_or_fail(upload_id, user_id))

    def create(
        self,
        *,
        user_id: int,
        name: str,
        kind: GarmentKind,
        content: bytes,
        max_bytes: int,
    ) -> GarmentUploadRead:
        extension = validate_image(content, max_bytes=max_bytes)

        try:
            imagen = Image.open(io.BytesIO(content))
            imagen.load()
        except Exception as exc:  # noqa: BLE001
            raise ValidationError("No se ha podido abrir la imagen.") from exc

        recorte = segmentar_prenda(imagen)

        # El original y la máscara se guardan por separado. La máscara es un
        # PNG en escala de grises: comprime muy bien y conserva el borde
        # suavizado, que un JPEG destrozaría con sus artefactos justo en el
        # canto, que es donde más se nota.
        buffer = io.BytesIO()
        recorte.mascara.save(buffer, format="PNG", optimize=True)

        upload = self.repository.create(
            user_id=user_id,
            name=name.strip(),
            kind=kind,
            image_key=self.storage.save(content, folder=FOLDER_UPLOADS, extension=extension),
            mask_key=self.storage.save(buffer.getvalue(), folder=FOLDER_MASKS, extension=".png"),
            mask_coverage=recorte.cobertura,
            mask_suspect=recorte.dudoso,
            width=imagen.width,
            height=imagen.height,
        )
        return self.to_read(upload)

    def delete(self, upload_id: int, user_id: int) -> None:
        upload = self._get_or_fail(upload_id, user_id)
        claves = [upload.image_key, upload.mask_key]

        # Primero la fila y después los archivos: al revés, un fallo al borrar
        # de la base dejaría una prenda en el catálogo apuntando a un archivo
        # que ya no existe, que es peor que un archivo huérfano.
        self.repository.delete(upload)
        for clave in claves:
            if clave:
                self.storage.delete(clave)

    def to_read(self, upload: GarmentUpload) -> GarmentUploadRead:
        return GarmentUploadRead(
            id=upload.id,
            user_id=upload.user_id,
            name=upload.name,
            kind=upload.kind,
            image_url=self.storage.public_url(upload.image_key),
            mask_url=self.storage.public_url(upload.mask_key),
            mask_coverage=upload.mask_coverage,
            width=upload.width,
            height=upload.height,
            mask_warning=self._aviso_de_recorte(upload),
            created_at=upload.created_at,
            updated_at=upload.updated_at,
        )

    @staticmethod
    def _aviso_de_recorte(upload: GarmentUpload) -> str | None:
        """Traduce la marca técnica en algo accionable.

        Decir «cobertura 0,02» no ayuda a nadie. Decir qué hacer, sí.
        """
        if not upload.mask_suspect:
            return None

        if upload.kind is GarmentKind.SKETCH:
            return (
                "El contorno del boceto parece tener algún hueco, y el recorte se ha "
                "colado por él. Repasa la línea exterior para que quede cerrada, o "
                "exporta el dibujo en PNG con el fondo transparente."
            )
        return (
            "La prenda es casi del mismo color que el fondo de la foto, así que no se "
            "ha podido separar bien y saldrá a tiras. Hace falta una fotografía sobre "
            "un fondo que contraste."
        )

    def _get_or_fail(self, upload_id: int, user_id: int) -> GarmentUpload:
        upload = self.repository.get_for_user(upload_id, user_id)
        if upload is None:
            # 404 aunque exista y sea de otro: un 403 confirmaría que existe, y
            # recorriendo identificadores se podrían contar los diseños ajenos.
            raise NotFoundError(f"No existe la prenda {upload_id}.")
        return upload
