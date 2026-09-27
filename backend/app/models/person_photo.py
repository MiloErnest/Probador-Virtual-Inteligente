"""La foto de una persona, para probarle prendas encima.

POR QUÉ ES UNA TABLA Y NO UN CAMPO DE LA PRUEBA
-----------------------------------------------
Quien se prueba ropa sube su foto UNA vez y después le prueba diez prendas. Si
la foto viviera dentro de cada prueba, serían diez copias del mismo archivo, y
borrarla —que es lo primero que alguien quiere poder hacer con una foto suya—
obligaría a encontrarlas todas.

Es la única imagen del proyecto que retrata a alguien, y eso decide dos cosas:

- **Se guarda sin metadatos.** Al subirla se vuelve a codificar, así que no
  viajan ni la ubicación GPS ni el modelo del teléfono que traiga la foto.
- **Borrarla borra también las pruebas hechas con ella** (cascada). Una prueba
  es esa persona con otra ropa: quedarse con el resultado después de que
  alguien haya retirado su foto sería quedarse con su foto.
"""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PersonPhoto(Base, TimestampMixin):
    __tablename__ = "person_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    image_key: Mapped[str] = mapped_column(String(512), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"<PersonPhoto id={self.id} {self.width}x{self.height}>"
