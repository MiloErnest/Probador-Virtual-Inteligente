"""Modelo de tela: el catálogo de la tienda textil.

POR QUÉ ESTA TABLA ES EL CENTRO DEL PRODUCTO
--------------------------------------------
El Product Vision Board describe una herramienta de venta para tiendas y
distribuidores de telas, cuyos usuarios son diseñadores, modistas y talleres
que tienen que **elegir tela para una prenda**. El catálogo, por tanto, no es
de ropa: es de TELA. La ropa la pone el usuario.

Eso invierte el modelo respecto al probador con cámara, donde el catálogo sí
era de prendas. Las dos cosas conviven: `garments` sigue siendo el catálogo del
probador y no se toca.

POR QUÉ TANTOS CAMPOS DE FICHA
------------------------------
Porque la métrica del producto es la conversión prueba→compra, y nadie compra
tela sin saber el ancho del rollo ni la composición. Una ficha con solo un
nombre y una foto sirve para un escaparate bonito, no para decidir una compra:
la modista necesita saber si con ese ancho le salen las piezas del patrón.
"""

import enum

from sqlalchemy import Boolean, Enum as SAEnum, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class FabricPattern(str, enum.Enum):
    """Cómo está dibujada la tela.

    No es decorativo: el motor de retexturizado lo usa para decidir la escala
    por defecto con que se repite el tejido sobre la prenda. Un liso da igual
    a qué tamaño se repita; un cuadro escocés a escala equivocada canta
    muchísimo.
    """

    SOLID = "solid"
    STRIPES = "stripes"
    CHECKS = "checks"
    PRINT = "print"
    TEXTURED = "textured"


class Fabric(Base, TimestampMixin):
    __tablename__ = "fabrics"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    # Referencia del proveedor. Es lo que la modista apunta para pedirla, así
    # que es el dato que convierte una prueba en un pedido.
    reference: Mapped[str | None] = mapped_column(String(64), default=None, index=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)

    # --- Ficha técnica ---
    composition: Mapped[str | None] = mapped_column(String(160), default=None)
    #: Gramaje en g/m². Distingue una gasa de una lona mejor que cualquier adjetivo.
    weight_gsm: Mapped[int | None] = mapped_column(Integer, default=None)
    #: Ancho del rollo en cm. Decide si salen las piezas del patrón.
    width_cm: Mapped[int | None] = mapped_column(Integer, default=None)

    # Numeric y no Float: el dinero con coma flotante acumula errores de
    # redondeo. Aquí solo se muestra y nunca se opera con él, pero guardarlo
    # bien cuesta lo mismo y evita el problema el día que haya un carrito.
    price_per_meter: Mapped[float | None] = mapped_column(Numeric(10, 2), default=None)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)

    # --- Aspecto ---
    color_name: Mapped[str | None] = mapped_column(String(80), default=None)
    #: Color dominante en #RRGGBB. Sirve para filtrar y para pintar la ficha
    #: mientras carga la imagen, sin esperar a la descarga.
    color_hex: Mapped[str | None] = mapped_column(String(7), default=None)
    pattern: Mapped[FabricPattern] = mapped_column(
        SAEnum(
            FabricPattern,
            native_enum=False,
            length=32,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=FabricPattern.SOLID,
        nullable=False,
        index=True,
    )

    # DOS IMÁGENES, Y NO SON LA MISMA COSA
    # ------------------------------------
    # `photo_key` es la foto de catálogo: la que se enseña en la tienda, con su
    # orillo, sus dobleces y a veces una mano sujetándola.
    #
    # `texture_key` es el MOSAICO: un trozo recortado que se repite sin costura
    # visible. Es lo que el motor estampa sobre la prenda. Usar la foto de
    # catálogo para eso metería el dobladillo y la mano dentro de la camisa.
    photo_key: Mapped[str | None] = mapped_column(String(512), default=None)
    texture_key: Mapped[str | None] = mapped_column(String(512), default=None)

    #: Cuántas veces se repite el mosaico a lo ancho de la prenda, por defecto.
    #: Es la escala del estampado, y depende del dibujo de cada tela.
    default_repeat: Mapped[int] = mapped_column(Integer, default=6, nullable=False)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<Fabric id={self.id} name={self.name!r} ref={self.reference!r}>"
