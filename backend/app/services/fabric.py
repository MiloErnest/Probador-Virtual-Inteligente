"""Reglas de negocio de las telas: el catálogo y las del propio taller.

Aquí también es donde `photo_key` y `texture_key` —claves internas— se
traducen a URLs públicas, para que ni las rutas ni el frontend sepan cómo se
almacenan los archivos.

DOS CLASES DE TELA, UNA SOLA TABLA
----------------------------------
Las del catálogo (`owner_id` vacío) las ve cualquiera y se gestionan por
`/api/fabrics`. Las de un taller (Ep6-Hu7 a Hu11) las ve solo su dueño y se
gestionan por `/api/my-fabrics`. Cada camino busca SOLO las suyas: una tela de
otro taller responde 404 en los dos, como si no existiera.
"""

# Sin esto, `list[...]` en un método escrito DESPUÉS de `def list` se refiere
# a ese método y no al tipo, y la clase no llega a importarse.
from __future__ import annotations

import base64
import io

from PIL import Image, ImageOps

from app.models.fabric import Fabric, FabricPattern
from app.repositories.fabric import FabricRepository
from app.schemas.fabric import (
    FabricCreate,
    FabricPreview,
    FabricRead,
    FabricUpdate,
    OwnFabricCreated,
    OwnFabricUpdate,
)
from app.services.exceptions import ConflictError, NotFoundError, ValidationError
from app.services.images import validate_image
from app.services.storage import FOLDER_FABRICS, Storage
from app.textil import tela_propia
from app.textil.errores import ErrorDeMotor

#: Lado mayor con que se guarda la foto de una tela del taller. El mosaico sale
#: a 1024 px del 80% central; guardar más solo ocupa disco.
LADO_DE_LA_FOTO = 2000


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
        #
        # Y SOLO si la otra imagen de la tela no es ese mismo archivo. La
        # semilla usa un único archivo para foto y mosaico, y borrar uno se
        # llevaba el otro: once telas del catálogo se quedaron sin foto así.
        otra = tela.photo_key if es_mosaico else tela.texture_key
        if anterior and anterior != otra:
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
            own=tela.owner_id is not None,
            created_at=tela.created_at,
            updated_at=tela.updated_at,
        )

    def _get_or_fail(self, fabric_id: int) -> Fabric:
        """Una tela del CATÁLOGO. Las de un taller no se ven ni se tocan por aquí."""
        tela = self.repository.get_catalog(fabric_id)
        if tela is None:
            raise NotFoundError(f"No existe la tela {fabric_id}.")
        return tela

    # --- Las telas del propio taller ---------------------------------------

    def preview_own(self, *, content: bytes, max_bytes: int, tipo: FabricPattern) -> FabricPreview:
        """Calcula el mosaico de una foto sin guardar nada (Ep6-Hu9 y Hu10)."""
        hecha = self._digitalizar(content, max_bytes=max_bytes, tipo=tipo)[1]
        buffer = io.BytesIO()
        hecha.mosaico.save(buffer, format="JPEG", quality=88)
        return FabricPreview(
            mosaic_data_url="data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode(),
            color_hex=hecha.color_hex,
            seam=round(hecha.junta, 2),
            seam_limit=tela_propia.JUNTA_MAXIMA,
            seam_visible=hecha.junta_visible,
            warnings=hecha.avisos,
        )

    def create_own(
        self,
        owner_id: int,
        *,
        name: str,
        tipo: FabricPattern,
        content: bytes,
        max_bytes: int,
        composition: str | None = None,
        default_repeat: int = 6,
    ) -> OwnFabricCreated:
        """Da de alta una tela del taller a partir de su foto (Ep6-Hu7).

        No llama a ningún modelo generativo: el mosaico lo calcula el motor
        determinista de `digitalizar.py`, el mismo que sacó las telas reales de
        la tienda de sus fotos. No cuesta dinero.
        """
        nombre = name.strip()
        if not nombre:
            raise ValidationError("La tela necesita un nombre.")
        if self.repository.get_by_name_for_owner(nombre, owner_id) is not None:
            raise ConflictError(f"Ya tienes una tela llamada «{nombre}».")

        foto, hecha = self._digitalizar(content, max_bytes=max_bytes, tipo=tipo)

        # La foto se vuelve a codificar desde los píxeles: así no se guarda nada
        # de lo que el móvil escribe en los metadatos, como la ubicación.
        buffer = io.BytesIO()
        foto.save(buffer, format="JPEG", quality=90)
        clave_foto = self.storage.save(buffer.getvalue(), folder=FOLDER_FABRICS, extension=".jpg")

        # PNG para el mosaico: la trama de una lisa es un relieve de un 6%, y
        # el JPEG lo convierte en bloques que después se repiten por la prenda.
        buffer = io.BytesIO()
        hecha.mosaico.save(buffer, format="PNG", optimize=True)
        clave_mosaico = self.storage.save(buffer.getvalue(), folder=FOLDER_FABRICS, extension=".png")

        tela = self.repository.create(
            name=nombre,
            composition=(composition or "").strip() or None,
            color_hex=hecha.color_hex,
            pattern=tipo,
            photo_key=clave_foto,
            texture_key=clave_mosaico,
            default_repeat=default_repeat,
            owner_id=owner_id,
            active=True,
        )
        return OwnFabricCreated(
            **self.to_read(tela).model_dump(), warnings=hecha.avisos, seam=round(hecha.junta, 2)
        )

    def list_own(self, owner_id: int, *, include_retired: bool = False) -> list[FabricRead]:
        return [
            self.to_read(t)
            for t in self.repository.list_for_owner(owner_id, include_retired=include_retired)
        ]

    def get_own(self, fabric_id: int, owner_id: int) -> FabricRead:
        return self.to_read(self._get_own_or_fail(fabric_id, owner_id))

    def update_own(self, fabric_id: int, owner_id: int, data: OwnFabricUpdate) -> FabricRead:
        """Edita el nombre, la composición, la descripción o la repetición (Ep6-Hu11)."""
        tela = self._get_own_or_fail(fabric_id, owner_id)
        cambios = data.model_dump(exclude_unset=True)

        if "name" in cambios:
            nombre = (cambios["name"] or "").strip()
            if not nombre:
                raise ValidationError("La tela necesita un nombre.")
            otra = self.repository.get_by_name_for_owner(nombre, owner_id)
            if otra is not None and otra.id != tela.id:
                raise ConflictError(f"Ya tienes una tela llamada «{nombre}».")
            cambios["name"] = nombre
        if "composition" in cambios:
            cambios["composition"] = (cambios["composition"] or "").strip() or None
        if cambios.get("default_repeat", 0) is None:
            del cambios["default_repeat"]

        for campo, valor in cambios.items():
            setattr(tela, campo, valor)
        return self.to_read(self.repository.save(tela))

    def delete_own(self, fabric_id: int, owner_id: int) -> bool:
        """Borra una tela del taller. Devuelve si se borró del todo.

        LAS PRUEBAS HECHAS CON ELLA SE CONSERVAN
        ----------------------------------------
        `fabric_trials.fabric_id` es RESTRICT: la base no deja borrar una tela
        con pruebas, y es lo que se quiere, porque esas pruebas son trabajo del
        usuario. Así que una tela con pruebas se RETIRA (`active = false`): deja
        de salir para elegir y en su lista, y sus pruebas siguen enseñando su
        nombre y su imagen. Una tela sin pruebas se borra de verdad, archivos
        incluidos.
        """
        tela = self._get_own_or_fail(fabric_id, owner_id)
        if self.repository.count_trials(tela.id) > 0:
            tela.active = False
            self.repository.save(tela)
            return False

        claves = [k for k in (tela.photo_key, tela.texture_key) if k]
        self.repository.delete(tela)
        for clave in claves:
            self.storage.delete(clave)
        return True

    def _get_own_or_fail(self, fabric_id: int, owner_id: int) -> Fabric:
        """Una tela ACTIVA de este usuario. Una ajena o borrada responde 404, no
        403: un 403 confirmaría que existe, y la tela de un taller es su trabajo."""
        tela = self.repository.get_for_owner(fabric_id, owner_id)
        if tela is None or not tela.active:
            raise NotFoundError(f"No existe la tela {fabric_id}.")
        return tela

    def _digitalizar(
        self, content: bytes, *, max_bytes: int, tipo: FabricPattern
    ) -> tuple[Image.Image, tela_propia.TelaDigitalizada]:
        validate_image(content, max_bytes=max_bytes)
        if tipo.value not in tela_propia.TIPOS:
            raise ValidationError(
                "Para una tela de tu taller elige lisa, de rayas o estampada. "
                "Un cuadro va como estampada: su repetición se reconoce sola."
            )
        with Image.open(io.BytesIO(content)) as abierta:
            # El móvil guarda la foto de lado y apunta el giro en los
            # metadatos. El navegador lo respeta; Pillow no, si no se le pide.
            foto = ImageOps.exif_transpose(abierta).convert("RGB")
        # Se reduce ANTES de medir: una foto de móvil de 12 Mpx tardaba varios
        # segundos en el desenfoque de la luz, y el mosaico sale a 1024 px igual.
        foto.thumbnail((LADO_DE_LA_FOTO, LADO_DE_LA_FOTO), Image.Resampling.LANCZOS)
        try:
            return foto, tela_propia.digitalizar(foto, tipo.value)
        except ErrorDeMotor as exc:
            raise ValidationError(str(exc)) from exc
