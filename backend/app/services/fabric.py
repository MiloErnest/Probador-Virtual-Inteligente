"""Reglas de negocio del catálogo de telas.

Aquí también es donde `photo_key` y `texture_key` —claves internas— se
traducen a URLs públicas, para que ni las rutas ni el frontend sepan cómo se
almacenan los archivos.
"""

from app.models.fabric import Fabric, FabricPattern
from app.repositories.fabric import FabricRepository
from app.schemas.fabric import FabricCreate, FabricRead, FabricUpdate
from app.services.exceptions import ConflictError, NotFoundError
from app.services.images import validate_image
from app.services.storage import FOLDER_FABRICS, Storage


class FabricService:
    def __init__(self, repository: FabricRepository, storage: Storage) -> None:
        self.repository = repository
        self.storage = storage

    # --- Consultas ---

    def list(
        self,
        *,
        pattern: FabricPattern | None = None,
        include_inactive: bool = False,
        only_probable: bool = False,
        limit: int = 60,
        offset: int = 0,
    ) -> list[FabricRead]:
        telas = self.repository.list(
            pattern=pattern,
            only_active=not include_inactive,
            only_probable=only_probable,
            limit=limit,
            offset=offset,
        )
        return [self.to_read(t) for t in telas]

    def get(self, fabric_id: int) -> FabricRead:
        return self.to_read(self._get_or_fail(fabric_id))

    # --- Comandos ---

    def create(self, data: FabricCreate) -> FabricRead:
        nombre = data.name.strip()
        if self.repository.get_by_name(nombre) is not None:
            # 409 y no 422: la petición es válida, lo que pasa es que ya
            # existe. Distinguirlo permite al frontend ofrecer «ver la que ya
            # tienes» en lugar de decir que los datos están mal.
            raise ConflictError(f"Ya hay una tela llamada «{nombre}» en el catálogo.")

        return self.to_read(
            self.repository.create(
                name=nombre,
                reference=data.reference,
                description=data.description,
                composition=data.composition,
                weight_gsm=data.weight_gsm,
                width_cm=data.width_cm,
                price_per_meter=data.price_per_meter,
                currency=data.currency.upper(),
                color_name=data.color_name,
                color_hex=data.color_hex.lower() if data.color_hex else None,
                pattern=data.pattern,
                default_repeat=data.default_repeat,
                active=data.active,
            )
        )

    def update(self, fabric_id: int, data: FabricUpdate) -> FabricRead:
        tela = self._get_or_fail(fabric_id)
        cambios = data.model_dump(exclude_unset=True)

        if "color_hex" in cambios and cambios["color_hex"]:
            cambios["color_hex"] = cambios["color_hex"].lower()
        if "name" in cambios and cambios["name"]:
            cambios["name"] = cambios["name"].strip()

        for campo, valor in cambios.items():
            setattr(tela, campo, valor)

        return self.to_read(self.repository.save(tela))

    def set_image(
        self, fabric_id: int, *, content: bytes, max_bytes: int, es_mosaico: bool
    ) -> FabricRead:
        """Guarda la foto de catálogo o el mosaico.

        Son dos imágenes distintas y la diferencia importa: la foto es la que
        se enseña en la ficha, con su orillo y sus dobleces; el mosaico es el
        cuadrado limpio que se repite sobre la prenda. Usar la foto como
        mosaico mete el dobladillo dentro de la camisa, repetido cuarenta
        veces.
        """
        tela = self._get_or_fail(fabric_id)
        extension = validate_image(content, max_bytes=max_bytes)

        anterior = tela.texture_key if es_mosaico else tela.photo_key
        nueva = self.storage.save(content, folder=FOLDER_FABRICS, extension=extension)

        if es_mosaico:
            tela.texture_key = nueva
        else:
            tela.photo_key = nueva
        self.repository.save(tela)

        # Se borra la anterior solo tras persistir la nueva, para no dejar la
        # tela sin imagen si la escritura en base de datos falla.
        if anterior:
            self.storage.delete(anterior)

        return self.to_read(tela)

    # --- Traducción modelo -> contrato público ---

    def to_read(self, tela: Fabric) -> FabricRead:
        return FabricRead(
            id=tela.id,
            name=tela.name,
            reference=tela.reference,
            description=tela.description,
            composition=tela.composition,
            weight_gsm=tela.weight_gsm,
            width_cm=tela.width_cm,
            # NUMERIC llega como Decimal; el contrato lo publica como número.
            price_per_meter=float(tela.price_per_meter) if tela.price_per_meter is not None else None,
            currency=tela.currency,
            color_name=tela.color_name,
            color_hex=tela.color_hex,
            pattern=tela.pattern,
            photo_url=self.storage.public_url(tela.photo_key),
            texture_url=self.storage.public_url(tela.texture_key),
            default_repeat=tela.default_repeat,
            active=tela.active,
            created_at=tela.created_at,
            updated_at=tela.updated_at,
        )

    def _get_or_fail(self, fabric_id: int) -> Fabric:
        tela = self.repository.get_by_id(fabric_id)
        if tela is None:
            raise NotFoundError(f"No existe la tela {fabric_id}.")
        return tela
