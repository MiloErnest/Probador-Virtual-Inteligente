"""Almacenamiento de imágenes.

ESTRATEGIA
----------
La aplicación nunca escribe rutas de disco directamente. Todo pasa por la
interfaz `Storage`, que maneja *claves* opacas del tipo
`"garments/3f9a1c2b.jpg"`. La base de datos guarda esa clave; la URL pública
se calcula al servir la respuesta.

Consecuencia: sustituir disco local por S3, Cloudflare R2 o cualquier otro
backend consiste en escribir una nueva clase que cumpla el protocolo y
cambiar `get_storage()`. Ni los modelos, ni las rutas, ni los datos ya
almacenados necesitan cambiar.

Hoy se usa `LocalStorage`, que escribe bajo `backend/storage/` y expone los
archivos mediante el montaje estático `/media` de FastAPI. Es suficiente para
un despliegue en un solo servidor; deja de serlo en cuanto haya más de una
instancia de la aplicación (entonces tocará el backend remoto).
"""

import uuid
from pathlib import Path
from typing import Protocol

from app.core.config import settings

# Solo formatos que todos los navegadores saben pintar.
ALLOWED_IMAGE_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

# Carpetas lógicas dentro del almacén.
FOLDER_GARMENTS = "garments"    # catálogo del probador con cámara
FOLDER_FABRICS = "fabrics"      # catálogo de telas: foto y mosaico
FOLDER_UPLOADS = "uploads"      # prendas y bocetos que sube el usuario
FOLDER_MASKS = "masks"          # recorte de cada prenda subida, cacheado
FOLDER_TRIALS = "trials"        # resultados de las pruebas


class Storage(Protocol):
    """Contrato mínimo de un almacén de archivos."""

    def save(self, data: bytes, *, folder: str, extension: str) -> str:
        """Guarda los bytes y devuelve la clave generada."""
        ...

    def read(self, key: str) -> bytes:
        """Devuelve el contenido del archivo. Lanza FileNotFoundError si no está."""
        ...

    def delete(self, key: str) -> None:
        """Elimina el archivo. No falla si la clave no existe."""
        ...

    def public_url(self, key: str | None) -> str | None:
        """URL absoluta para consumir desde el navegador."""
        ...


class LocalStorage:
    """Implementación sobre el sistema de archivos local."""

    def __init__(self, root: Path, media_url_path: str, public_base_url: str) -> None:
        self.root = Path(root)
        self.media_url_path = media_url_path.rstrip("/")
        self.public_base_url = public_base_url.rstrip("/")

    def ensure_directories(self) -> None:
        for folder in (
            FOLDER_GARMENTS,
            FOLDER_FABRICS,
            FOLDER_UPLOADS,
            FOLDER_MASKS,
            FOLDER_TRIALS,
        ):
            (self.root / folder).mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, *, folder: str, extension: str) -> str:
        target_dir = self.root / folder
        target_dir.mkdir(parents=True, exist_ok=True)

        # Nombre aleatorio: evita colisiones y no filtra el nombre original
        # del archivo del usuario.
        filename = f"{uuid.uuid4().hex}{extension}"
        (target_dir / filename).write_bytes(data)
        return f"{folder}/{filename}"

    def read(self, key: str) -> bytes:
        # Pasa por `_resolve`, así que una clave manipulada del tipo
        # "../../.env" no sale del almacén.
        path = self._resolve(key)
        if path is None or not path.is_file():
            raise FileNotFoundError(f"No existe el archivo {key!r} en el almacén.")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path is not None:
            path.unlink(missing_ok=True)

    def public_url(self, key: str | None) -> str | None:
        if not key:
            return None
        return f"{self.public_base_url}{self.media_url_path}/{key}"

    def _resolve(self, key: str) -> Path | None:
        """Convierte una clave en ruta, rechazando intentos de path traversal."""
        candidate = (self.root / key).resolve()
        root = self.root.resolve()
        if root not in candidate.parents and candidate != root:
            return None
        return candidate


def get_storage() -> Storage:
    """Punto único de construcción del almacén.

    Cuando exista un backend remoto, aquí se elegirá según configuración.
    """
    return LocalStorage(
        root=settings.STORAGE_DIR,
        media_url_path=settings.MEDIA_URL_PATH,
        public_base_url=settings.PUBLIC_BASE_URL,
    )
