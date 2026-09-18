"""Modelo de la prueba: una prenda vestida con una tela.

ES LA UNIDAD DE NEGOCIO, NO UN REGISTRO TÉCNICO
-----------------------------------------------
El Vision Board mide el producto en «pruebas generadas» y «tasa de conversión
prueba→compra». Esta tabla es esa prueba. Por eso guarda cosas que un registro
puramente técnico no guardaría —qué motor la generó, cuánto costó— y por eso
no se borra al terminar: es el historial y la galería, que son dos de las
cinco características del documento.

POR QUÉ SE GUARDA EL COSTE
--------------------------
La API de OpenAI devuelve los tokens consumidos en cada llamada. Guardarlos
convierte «hay que controlar el gasto» en un número que se puede sumar,
enseñar y limitar. Con Gemini, en la etapa anterior, el gasto era una
preocupación escrita en un documento y nada más; se quedó anotado como riesgo
alto precisamente por eso.
"""

import enum

from sqlalchemy import (
    CheckConstraint,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TrialStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TrialMethod(str, enum.Enum):
    """Con qué motor se generó.

    Se guarda en la prueba y no solo en la configuración porque el historial
    tiene que poder explicarse a sí mismo: dos pruebas de la misma prenda
    pueden haberse hecho con motores distintos, y la diferencia de aspecto
    entre ellas se entiende sabiendo cuál es cuál.
    """

    #: Retexturizado determinista: se reutiliza la luz de la fotografía.
    RETEXTURE = "retexture"
    #: Generación con IA: la única vía para un boceto sin sombras.
    AI = "ai"


class FabricTrial(Base, TimestampMixin):
    __tablename__ = "fabric_trials"
    __table_args__ = (
        # Una escala de estampado de cero o negativa dejaría el motor
        # dividiendo por cero. Se corta en la base, no solo en Pydantic: la
        # base es la última que puede decir que no.
        CheckConstraint("repeat_across > 0", name="ck_fabric_trials_repeat_positivo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # RESTRICT y no CASCADE: borrar una tela del catálogo no debe destruir las
    # pruebas que alguien hizo con ella. Una tela se retira con `active=false`.
    garment_upload_id: Mapped[int] = mapped_column(
        ForeignKey("garment_uploads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fabric_id: Mapped[int] = mapped_column(
        ForeignKey("fabrics.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    status: Mapped[TrialStatus] = mapped_column(
        SAEnum(
            TrialStatus,
            native_enum=False,
            length=32,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=TrialStatus.PENDING,
        nullable=False,
        index=True,
    )
    method: Mapped[TrialMethod] = mapped_column(
        SAEnum(
            TrialMethod,
            native_enum=False,
            length=32,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=TrialMethod.RETEXTURE,
        nullable=False,
    )

    #: Cuántas veces se repite el mosaico a lo ancho de la prenda.
    repeat_across: Mapped[int] = mapped_column(Integer, default=6, nullable=False)

    output_image_key: Mapped[str | None] = mapped_column(String(512), default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    #: Algo que el usuario debería saber del resultado, sin llegar a ser un
    #: error. Se persiste y no se recalcula porque describe ESTA prueba: la
    #: misma prenda con otro motor puede no tener nada que advertir.
    notice: Mapped[str | None] = mapped_column(Text, default=None)
    provider: Mapped[str | None] = mapped_column(String(64), default=None)

    #: Tokens facturados por la llamada a la IA. Nulo en el motor determinista,
    #: que no cuesta nada, y esa diferencia se ve de un vistazo en la galería.
    tokens_used: Mapped[int | None] = mapped_column(Integer, default=None)
    #: Milisegundos que tardó el motor. Sirve para justificar por qué el camino
    #: determinista es el principal: es del orden de cien veces más rápido.
    duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)

    def __repr__(self) -> str:
        return f"<FabricTrial id={self.id} status={self.status.value} method={self.method.value}>"
