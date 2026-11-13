"""Reglas de negocio de las prendas que sube el usuario.

EL RECORTE SE HACE AL SUBIR, NO AL PROBAR
-----------------------------------------
Cuesta unos doscientos milisegundos y se necesita idéntico para cada tela. Si
se hiciera al probar, probar diez telas serían diez recortes iguales; haciéndolo
una vez, son diez multiplicaciones. Además permite avisar de un recorte malo
ANTES de que el usuario empiece a gastar pruebas sobre él.

UN BOCETO TARDA, Y POR ESO TIENE ESTADO
---------------------------------------
Una fotografía queda lista en la misma petición. Un boceto no es una prenda:
la IA tiene que generarla (`app/textil/boceto_ia.py`), y eso son unos cuarenta
segundos y dinero. Subirlo responde enseguida con la prenda en `pending`, la
generación corre en segundo plano y el cliente sondea, igual que con las
pruebas de tela.

CADA VARIANTE ES UNA PRENDA NUEVA
---------------------------------
«Otra variante» no pisa la prenda que ya hay: crea otra a partir del mismo
dibujo. Las telas ya probadas sobre la primera siguen siendo de la primera, y
el usuario borra la que no le convenza. Es lo mismo que hace el probador.
"""

import io
from pathlib import PurePosixPath

from PIL import Image

from app.core.config import settings
from app.models.garment_upload import GarmentKind, GarmentStatus, GarmentUpload
from app.repositories.fabric_trial import FabricTrialRepository
from app.repositories.garment_upload import GarmentUploadRepository
from app.schemas.garment_upload import GarmentUploadRead
from app.services.exceptions import NotFoundError, ValidationError
from app.services.images import validate_image
from app.services.storage import FOLDER_MASKS, FOLDER_UPLOADS, Storage
from app.textil import ErrorDeMotor, boceto_ia, segmentar_prenda


class GarmentUploadService:
    def __init__(
        self,
        repository: GarmentUploadRepository,
        trials: FabricTrialRepository,
        storage: Storage,
    ) -> None:
        self.repository = repository
        self.trials = trials
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

        if kind is GarmentKind.SKETCH:
            # El techo se comprueba ANTES de guardar nada: un boceto subido es
            # una imagen que se va a generar y a cobrar.
            self._comprobar_techo_de_gasto(user_id)
            return self.to_read(
                self._crear_boceto(user_id, name.strip(), content, extension, imagen.size)
            )

        recorte = segmentar_prenda(imagen)

        # El original y la máscara se guardan por separado. La máscara es un
        # PNG en escala de grises: comprime muy bien y conserva el borde
        # suavizado, que un JPEG destrozaría con sus artefactos justo en el
        # canto, que es donde más se nota.
        upload = self.repository.create(
            user_id=user_id,
            name=name.strip(),
            kind=kind,
            status=GarmentStatus.READY,
            image_key=self.storage.save(content, folder=FOLDER_UPLOADS, extension=extension),
            mask_key=self._guardar_mascara(recorte.mascara),
            mask_coverage=recorte.cobertura,
            mask_suspect=recorte.dudoso,
            width=imagen.width,
            height=imagen.height,
        )
        return self.to_read(upload)

    def otra_variante(self, upload_id: int, user_id: int) -> GarmentUploadRead:
        """Vuelve a generar la prenda de un boceto. Cada llamada se cobra.

        Si la prenda falló y no tiene nada colgando, se reintenta sobre la
        misma fila. En cualquier otro caso se crea una prenda nueva y la que
        había no se toca: sus pruebas de tela se hicieron sobre ELLA.
        """
        upload = self._get_or_fail(upload_id, user_id)
        if upload.kind is not GarmentKind.SKETCH or not upload.sketch_key:
            raise ValidationError(
                "Solo un boceto puede generar otra variante: una fotografía ya es la prenda."
            )
        if upload.status in (GarmentStatus.PENDING, GarmentStatus.PROCESSING):
            raise ValidationError("Esta prenda todavía se está generando. Espera a que termine.")

        self._comprobar_techo_de_gasto(user_id)

        if upload.status is GarmentStatus.FAILED and not self.repository.tiene_pruebas(upload.id):
            upload.status = GarmentStatus.PENDING
            upload.error_message = None
            return self.to_read(self.repository.save(upload))

        dibujo = self.storage.read(upload.sketch_key)
        with Image.open(io.BytesIO(dibujo)) as imagen:
            tamano = imagen.size
        extension = PurePosixPath(upload.sketch_key).suffix or ".png"
        return self.to_read(self._crear_boceto(user_id, upload.name, dibujo, extension, tamano))

    def delete(self, upload_id: int, user_id: int) -> None:
        upload = self._get_or_fail(upload_id, user_id)
        # Un conjunto: en un boceto sin generar, `image_key` y `sketch_key`
        # son el mismo archivo.
        claves = {upload.image_key, upload.sketch_key, upload.mask_key}
        claves |= set(self.repository.claves_de_sus_pruebas(upload.id))

        # Primero la fila y después los archivos: al revés, un fallo al borrar
        # de la base dejaría una prenda en el catálogo apuntando a un archivo
        # que ya no existe, que es peor que un archivo huérfano.
        self.repository.delete(upload)
        for clave in claves:
            if clave:
                self.storage.delete(clave)

    # --- Procesado en segundo plano ---

    def generar(self, upload_id: int) -> None:
        """Genera la prenda de un boceto. Corre fuera del ciclo de la petición."""
        upload = self.repository.get_by_id(upload_id)
        if upload is None or upload.status is not GarmentStatus.PENDING:
            # Ya la generó alguien, o se borró mientras esperaba. Repetirla
            # sería pagar dos veces por la misma prenda.
            return

        upload.status = GarmentStatus.PROCESSING
        self.repository.save(upload)

        try:
            boceto = Image.open(io.BytesIO(self.storage.read(upload.sketch_key)))
            boceto.load()
            resultado = boceto_ia.prenda_desde_boceto(boceto)
        except ErrorDeMotor as exc:
            upload.status = GarmentStatus.FAILED
            upload.error_message = str(exc)
        except Exception as exc:  # noqa: BLE001
            # Cualquier otra cosa es un fallo nuestro. Se guarda el tipo para
            # poder buscarlo en los registros, pero no la traza entera: acaba
            # en la pantalla del usuario.
            upload.status = GarmentStatus.FAILED
            upload.error_message = f"Error inesperado al generar la prenda ({type(exc).__name__})."
        else:
            # Un boceto antiguo llega aquí con el recorte de su DIBUJO, que ya
            # no vale: el nuevo es el de la prenda.
            mascara_vieja = upload.mask_key

            buffer = io.BytesIO()
            resultado.imagen.save(buffer, format="JPEG", quality=95, optimize=True)

            upload.image_key = self.storage.save(
                buffer.getvalue(), folder=FOLDER_UPLOADS, extension=".jpg"
            )
            upload.mask_key = self._guardar_mascara(resultado.recorte.mascara)
            upload.mask_coverage = resultado.recorte.cobertura
            upload.mask_suspect = resultado.recorte.dudoso
            upload.width, upload.height = resultado.imagen.size
            upload.similarity = round(resultado.parecido, 4)
            upload.provider = resultado.proveedor
            upload.tokens_used = resultado.tokens
            upload.error_message = None
            upload.status = GarmentStatus.READY

            if mascara_vieja:
                self.storage.delete(mascara_vieja)

        self.repository.save(upload)

    # --- Traducción y reglas auxiliares ---

    def to_read(self, upload: GarmentUpload) -> GarmentUploadRead:
        return GarmentUploadRead(
            id=upload.id,
            user_id=upload.user_id,
            name=upload.name,
            kind=upload.kind,
            status=upload.status,
            image_url=self.storage.public_url(upload.image_key),
            sketch_url=self.storage.public_url(upload.sketch_key),
            mask_url=self.storage.public_url(upload.mask_key),
            mask_coverage=upload.mask_coverage,
            width=upload.width,
            height=upload.height,
            mask_warning=self._aviso_de_recorte(upload),
            error_message=upload.error_message,
            similarity=upload.similarity,
            similarity_warning=self._aviso_de_parecido(upload),
            tokens_used=upload.tokens_used,
            created_at=upload.created_at,
            updated_at=upload.updated_at,
        )

    def _crear_boceto(
        self, user_id: int, name: str, dibujo: bytes, extension: str, tamano: tuple[int, int]
    ) -> GarmentUpload:
        clave = self.storage.save(dibujo, folder=FOLDER_UPLOADS, extension=extension)
        return self.repository.create(
            user_id=user_id,
            name=name,
            kind=GarmentKind.SKETCH,
            status=GarmentStatus.PENDING,
            # Mientras no hay prenda, la imagen es el propio dibujo.
            image_key=clave,
            sketch_key=clave,
            width=tamano[0],
            height=tamano[1],
        )

    def _guardar_mascara(self, mascara: Image.Image) -> str:
        buffer = io.BytesIO()
        mascara.save(buffer, format="PNG", optimize=True)
        return self.storage.save(buffer.getvalue(), folder=FOLDER_MASKS, extension=".png")

    def _comprobar_techo_de_gasto(self, user_id: int) -> None:
        # El techo es uno solo: suma las prendas generadas a partir de bocetos
        # y las pruebas con IA, que salen de la misma cuenta.
        usadas = self.repository.contar_bocetos_generados_hoy(
            user_id
        ) + self.trials.contar_ia_hoy(user_id)
        if usadas >= settings.AI_TRIALS_PER_USER_PER_DAY:
            raise ValidationError(
                f"Has llegado al límite de {settings.AI_TRIALS_PER_USER_PER_DAY} "
                "usos de la IA en 24 horas. Probar telas sobre las prendas que ya "
                "tienes no gasta nada y no tiene límite."
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
                "La prenda generada no se ha podido separar bien de su fondo, así que "
                "la tela saldrá a tiras. Pide otra variante."
            )
        return (
            "La prenda es casi del mismo color que el fondo de la foto, así que no se "
            "ha podido separar bien y saldrá a tiras. Hace falta una fotografía sobre "
            "un fondo que contraste."
        )

    @staticmethod
    def _aviso_de_parecido(upload: GarmentUpload) -> str | None:
        """Si la silueta se aparta del dibujo, se dice — con el número."""
        if upload.similarity is None or upload.similarity >= boceto_ia.PARECIDO_MINIMO:
            return None
        return (
            f"La silueta de esta prenda coincide solo en un {upload.similarity:.0%} con "
            "la de tu boceto: la IA se ha apartado del dibujo. Compáralas antes de "
            "usarla, o pide otra variante."
        )

    def _get_or_fail(self, upload_id: int, user_id: int) -> GarmentUpload:
        upload = self.repository.get_for_user(upload_id, user_id)
        if upload is None:
            # 404 aunque exista y sea de otro: un 403 confirmaría que existe, y
            # recorriendo identificadores se podrían contar los diseños ajenos.
            raise NotFoundError(f"No existe la prenda {upload_id}.")
        return upload
