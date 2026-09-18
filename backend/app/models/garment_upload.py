"""Modelo de la prenda que sube el usuario.

QUÉ ES Y QUÉ NO ES
------------------
Esto NO es el catálogo. El catálogo son las telas (`fabrics`). Esto es el
diseño que trae el usuario: la foto de una prenda que ya existe, o el boceto
de una que todavía no.

Es deliberadamente de cada usuario y no compartido: el boceto de un diseñador
es su trabajo, y el Vision Board habla de talleres y modistas que compiten
entre sí.

LA DISTINCIÓN FOTO/BOCETO NO ES UNA ETIQUETA
--------------------------------------------
Decide qué motor puede vestir la prenda, y por una razón física:

- Una FOTOGRAFÍA ya trae los pliegues, las sombras y los brillos reales. El
  motor determinista extrae ese mapa de luz y multiplica la tela nueva por él:
  la tela cae siguiendo los pliegues de verdad de esa prenda. Sale gratis, es
  instantáneo y da siempre el mismo resultado.

- Un BOCETO es un dibujo de líneas: no tiene sombras. No hay nada que
  multiplicar, así que el volumen y la caída hay que inventarlos. Ahí la IA
  generativa no es un adorno, es la única forma de hacerlo.

Por eso el campo existe y por eso se pregunta al subir.
"""

import enum

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class GarmentKind(str, enum.Enum):
    PHOTO = "photo"
    SKETCH = "sketch"


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

    image_key: Mapped[str] = mapped_column(String(512), nullable=False)

    # LA MÁSCARA SE GUARDA, NO SE RECALCULA
    # -------------------------------------
    # Recortar la prenda del fondo cuesta más de un segundo, y se necesita
    # exactamente igual para cada tela que se pruebe. Calcularla una vez al
    # subir y guardarla convierte «probar diez telas» en diez multiplicaciones
    # en vez de diez recortes.
    #
    # Nula mientras el recorte está en marcha, o si falló.
    mask_key: Mapped[str | None] = mapped_column(String(512), default=None)

    #: Fracción de la imagen que ocupa la prenda, de 0 a 1. Si es ridícula, el
    #: recorte salió mal y conviene avisar antes de que el usuario pruebe diez
    #: telas sobre una máscara rota.
    mask_coverage: Mapped[float | None] = mapped_column(default=None)

    #: El recorte salió dudoso: la prenda era casi del color del fondo, o el
    #: contorno del boceto tenía un hueco por el que se coló el relleno. Se
    #: guarda al subir para poder avisar ANTES de que alguien gaste diez
    #: pruebas sobre una máscara rota.
    mask_suspect: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    #: Ancho y alto originales. Evita abrir el archivo solo para saber si la
    #: imagen es apaisada, que es lo que decide el tamaño que se le pide a la IA.
    width: Mapped[int | None] = mapped_column(Integer, default=None)
    height: Mapped[int | None] = mapped_column(Integer, default=None)

    def __repr__(self) -> str:
        return f"<GarmentUpload id={self.id} name={self.name!r} kind={self.kind.value}>"
