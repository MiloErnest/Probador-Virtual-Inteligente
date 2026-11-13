"""Modelo de la prenda que sube el usuario.

QUÉ ES Y QUÉ NO ES
------------------
Esto NO es el catálogo. El catálogo son las telas (`fabrics`). Esto es el
diseño que trae el usuario: la foto de una prenda que ya existe, o el boceto
de una que todavía no.

Es deliberadamente de cada usuario y no compartido: el boceto de un diseñador
es su trabajo, y el Vision Board habla de talleres y modistas que compiten
entre sí.

LA DISTINCIÓN FOTO/BOCETO DICE DE DÓNDE SALE LA PRENDA
------------------------------------------------------
- Una FOTOGRAFÍA es ya la prenda. Se recorta al subir y queda lista.

- Un BOCETO no es una prenda: es el dibujo de una. La IA generativa lo
  convierte en la fotografía de esa prenda (`app/textil/boceto_ia.py`), y es
  esa fotografía la que queda en `image_key`. El dibujo se conserva en
  `sketch_key`, para enseñarlos lado a lado y para poder pedir otra variante.

A partir de ahí las dos se visten igual, con el motor determinista: lo que
cambia entre dos pruebas de la misma prenda es solo la tela.

Hubo un camino intermedio —pintar la tela sobre el propio dibujo— que se
retiró: un boceto con una tela encima sigue siendo un boceto.
"""

import enum

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class GarmentKind(str, enum.Enum):
    PHOTO = "photo"
    SKETCH = "sketch"


class GarmentStatus(str, enum.Enum):
    """En qué punto está la prenda. Solo `ready` se puede probar.

    Una fotografía nace `ready`. Un boceto pasa por los otros estados mientras
    la IA genera su prenda, que tarda del orden de medio minuto.
    """

    READY = "ready"
    PENDING = "pending"
    PROCESSING = "processing"
    FAILED = "failed"


class GarmentUpload(Base, TimestampMixin):
    __tablename__ = "garment_uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    kind: Mapped[GarmentKind] = mapped_column(
        SAEnum(
            GarmentKind,
            native_enum=False,
            length=32,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=GarmentKind.PHOTO,
        nullable=False,
    )

    status: Mapped[GarmentStatus] = mapped_column(
        SAEnum(
            GarmentStatus,
            native_enum=False,
            length=32,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=GarmentStatus.READY,
        server_default=GarmentStatus.READY.value,
        nullable=False,
    )

    #: La imagen sobre la que se prueban las telas. En una fotografía, la que
    #: subió el usuario. En un boceto, la prenda generada; mientras no la hay
    #: apunta al propio dibujo, para que la columna nunca esté vacía.
    image_key: Mapped[str] = mapped_column(String(512), nullable=False)

    #: El dibujo original. Nulo en una fotografía.
    sketch_key: Mapped[str | None] = mapped_column(String(512), default=None)

    # LA MÁSCARA SE GUARDA, NO SE RECALCULA
    # -------------------------------------
    # Recortar la prenda del fondo cuesta más de un segundo, y se necesita
    # exactamente igual para cada tela que se pruebe. Calcularla una vez al
    # subir y guardarla convierte «probar diez telas» en diez multiplicaciones
    # en vez de diez recortes.
    #
    # Nula mientras la prenda de un boceto no está generada, o si falló.
    mask_key: Mapped[str | None] = mapped_column(String(512), default=None)

    #: Fracción de la imagen que ocupa la prenda, de 0 a 1. Si es ridícula, el
    #: recorte salió mal y conviene avisar antes de que el usuario pruebe diez
    #: telas sobre una máscara rota.
    mask_coverage: Mapped[float | None] = mapped_column(default=None)

    #: El recorte salió dudoso: la prenda era casi del color del fondo. Se
    #: guarda al subir para poder avisar ANTES de que alguien gaste diez
    #: pruebas sobre una máscara rota.
    mask_suspect: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    #: Ancho y alto de `image_key`.
    width: Mapped[int | None] = mapped_column(Integer, default=None)
    height: Mapped[int | None] = mapped_column(Integer, default=None)

    # --- Solo en un boceto: lo que dejó la generación ---

    #: Por qué no se pudo generar la prenda, dicho para el usuario.
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    #: Coincidencia de la silueta de la prenda con la del dibujo, de 0 a 1.
    #: Mide el contorno y nada de dentro: acompaña a la comparación a ojo.
    similarity: Mapped[float | None] = mapped_column(default=None)

    provider: Mapped[str | None] = mapped_column(String(64), default=None)
    #: Tokens facturados por la generación. El gasto es un número que se suma.
    tokens_used: Mapped[int | None] = mapped_column(Integer, default=None)

    def __repr__(self) -> str:
        return f"<GarmentUpload id={self.id} name={self.name!r} kind={self.kind.value}>"
