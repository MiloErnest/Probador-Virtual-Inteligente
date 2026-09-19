"""Reglas de negocio de las pruebas de tela.

EL CICLO
--------
Crear una prueba responde 202 con estado `pending`: el resultado no viene en
esa respuesta. Se procesa en segundo plano y el cliente sondea hasta que el
estado sea `completed` o `failed`.

Podría parecer excesivo para un motor que tarda medio segundo, y para ese
camino lo es. Pero el motor generativo tarda entre diez y treinta, y mantener
dos contratos distintos —uno síncrono y otro asíncrono— para la misma acción
obligaría al frontend a saber qué motor va a correr antes de pedirlo. Con uno
solo, la pantalla es la misma y el motor es un detalle.
"""

import io
import time

from PIL import Image

from app.core.config import settings
from app.models.fabric_trial import FabricTrial, TrialMethod, TrialStatus
from app.models.garment_upload import GarmentKind
from app.repositories.fabric import FabricRepository
from app.repositories.fabric_trial import FabricTrialRepository
from app.repositories.garment_upload import GarmentUploadRepository
from app.schemas.fabric_trial import TrialCreate, TrialRead
from app.services.exceptions import NotFoundError, ValidationError
from app.services.storage import FOLDER_TRIALS, Storage
from app.textil import ErrorDeMotor, PeticionDeTela, motor_para


class FabricTrialService:
    def __init__(
        self,
        repository: FabricTrialRepository,
        uploads: GarmentUploadRepository,
        fabrics: FabricRepository,
        storage: Storage,
    ) -> None:
        self.repository = repository
        self.uploads = uploads
        self.fabrics = fabrics
        self.storage = storage

    # --- Consultas ---

    def list(
        self,
        user_id: int,
        *,
        garment_upload_id: int | None = None,
        limit: int = 60,
        offset: int = 0,
    ) -> list[TrialRead]:
        pruebas = self.repository.list_for_user(
            user_id, garment_upload_id=garment_upload_id, limit=limit, offset=offset
        )
        return [self.to_read(p) for p in pruebas]

    def get(self, trial_id: int, user_id: int) -> TrialRead:
        return self.to_read(self._get_or_fail(trial_id, user_id))

    # --- Comandos ---

    def create(self, user_id: int, data: TrialCreate) -> TrialRead:
        prenda = self.uploads.get_for_user(data.garment_upload_id, user_id)
        if prenda is None:
            raise NotFoundError(f"No existe la prenda {data.garment_upload_id}.")

        tela = self.fabrics.get_by_id(data.fabric_id)
        if tela is None or not tela.active:
            raise NotFoundError(f"No existe la tela {data.fabric_id}.")

        metodo = data.method or self._motor_por_defecto(prenda.kind)

        if metodo is TrialMethod.RETEXTURE and tela.texture_key is None:
            raise ValidationError(
                f"La tela «{tela.name}» no tiene mosaico cargado, así que no se puede "
                "estampar. Súbele uno desde el catálogo, o prueba con el motor de IA."
            )

        if metodo is TrialMethod.AI:
            self._comprobar_techo_de_gasto(user_id)

        return self.to_read(
            self.repository.create(
                user_id=user_id,
                garment_upload_id=prenda.id,
                fabric_id=tela.id,
                method=metodo,
                repeat_across=data.repeat_across or tela.default_repeat,
                status=TrialStatus.PENDING,
            )
        )

    def delete(self, trial_id: int, user_id: int) -> None:
        prueba = self._get_or_fail(trial_id, user_id)
        clave = prueba.output_image_key
        self.repository.delete(prueba)
        if clave:
            self.storage.delete(clave)

    # --- Procesado en segundo plano ---

    def process(self, trial_id: int) -> None:
        """Genera el resultado. Corre fuera del ciclo de la petición."""
        prueba = self.repository.get_by_id(trial_id)
        if prueba is None or prueba.status is not TrialStatus.PENDING:
            # Ya la procesó alguien, o se borró mientras esperaba. Volver a
            # procesarla duplicaría el gasto en el camino de la IA.
            return

        prueba.status = TrialStatus.PROCESSING
        self.repository.save(prueba)

        comenzado = time.perf_counter()
        try:
            resultado = self._ejecutar(prueba)
        except (ErrorDeMotor, ValidationError) as exc:
            # El motor lanza lo suyo y aquí se traduce. Es lo que permite que
            # `app/textil/` no sepa que existe una capa de servicios encima.
            prueba.status = TrialStatus.FAILED
            prueba.error_message = str(exc)
        except Exception as exc:  # noqa: BLE001
            # Cualquier otra cosa es un fallo nuestro. Se guarda el tipo para
            # poder buscarlo en los registros, pero no la traza entera: acaba
            # en la pantalla del usuario.
            prueba.status = TrialStatus.FAILED
            prueba.error_message = f"Error inesperado del motor ({type(exc).__name__})."
        else:
            buffer = io.BytesIO()
            resultado.imagen.save(buffer, format="JPEG", quality=92, optimize=True)

            prueba.status = TrialStatus.COMPLETED
            prueba.output_image_key = self.storage.save(
                buffer.getvalue(), folder=FOLDER_TRIALS, extension=".jpg"
            )
            prueba.provider = resultado.proveedor
            prueba.tokens_used = resultado.tokens
            prueba.notice = resultado.aviso

        prueba.duration_ms = int((time.perf_counter() - comenzado) * 1000)
        self.repository.save(prueba)

    def _ejecutar(self, prueba: FabricTrial):
        prenda = self.uploads.get_by_id(prueba.garment_upload_id)
        tela = self.fabrics.get_by_id(prueba.fabric_id)
        if prenda is None or tela is None:
            raise ValidationError("La prenda o la tela ya no existen.")

        imagen = Image.open(io.BytesIO(self.storage.read(prenda.image_key)))
        imagen.load()

        if prenda.mask_key is None:
            raise ValidationError("Esta prenda no tiene recorte; vuelve a subirla.")
        mascara = Image.open(io.BytesIO(self.storage.read(prenda.mask_key)))
        mascara.load()

        mosaico = None
        if tela.texture_key:
            mosaico = Image.open(io.BytesIO(self.storage.read(tela.texture_key)))
            mosaico.load()

        motor = motor_para(prueba.method)
        return motor.aplicar(
            PeticionDeTela(
                prenda=imagen,
                mascara=mascara,
                caja=_caja_de(mascara),
                tipo=prenda.kind,
                mosaico=mosaico,
                descripcion=_describir(tela),
                repeticiones=prueba.repeat_across,
            )
        )

    # --- Traducción y reglas auxiliares ---

    def to_read(self, prueba: FabricTrial) -> TrialRead:
        return TrialRead(
            id=prueba.id,
            user_id=prueba.user_id,
            garment_upload_id=prueba.garment_upload_id,
            fabric_id=prueba.fabric_id,
            status=prueba.status,
            method=prueba.method,
            repeat_across=prueba.repeat_across,
            output_image_url=self.storage.public_url(prueba.output_image_key),
            error_message=prueba.error_message,
            provider=prueba.provider,
            tokens_used=prueba.tokens_used,
            duration_ms=prueba.duration_ms,
            notice=prueba.notice,
            created_at=prueba.created_at,
            updated_at=prueba.updated_at,
        )

    @staticmethod
    def _motor_por_defecto(tipo: GarmentKind) -> TrialMethod:
        """Qué motor corre si nadie lo dice: SIEMPRE el que no cuesta dinero.

        Al principio los bocetos iban a la IA por defecto, porque un dibujo no
        tiene sombras que reutilizar. Se probó contra la API real —con el
        modelo mini, con el completo y con `input_fidelity="high"`— y el
        resultado fue el mismo las tres veces: el modelo devolvía una prenda
        distinta. Un boceto con cartera de botones, bolsillo y cuello camisero
        volvía convertido en una túnica lisa de cuello barco.

        Para un producto que promete «mira TU diseño con otra tela», eso es el
        resultado equivocado, y además se cobraba por él. Así que el boceto
        tiene ahora su propio camino determinista, que conserva el trazo.

        La IA sigue estando, y para lo que sí sabe hacer: convertir el dibujo
        en algo fotorrealista. Pero se pide a conciencia.
        """
        return TrialMethod.RETEXTURE

    def _get_or_fail(self, trial_id: int, user_id: int) -> FabricTrial:
        prueba = self.repository.get_for_user(trial_id, user_id)
        if prueba is None:
            # 404 aunque exista y sea de otro: un 403 confirmaría que existe.
            raise NotFoundError(f"No existe la prueba {trial_id}.")
        return prueba

    def _comprobar_techo_de_gasto(self, user_id: int) -> None:
        usadas = self.repository.contar_ia_hoy(user_id)
        if usadas >= settings.AI_TRIALS_PER_USER_PER_DAY:
            raise ValidationError(
                f"Has llegado al límite de {settings.AI_TRIALS_PER_USER_PER_DAY} "
                "pruebas con IA en 24 horas. Las pruebas sobre fotografías no "
                "gastan nada y no tienen límite."
            )


def _caja_de(mascara: Image.Image) -> tuple[int, int, int, int]:
    """Caja que ocupa la prenda dentro de la máscara.

    Es lo que fija la escala del estampado. Si se usara la imagen entera, la
    misma tela cambiaría de tamaño según el margen que tuviera la foto, y dos
    pruebas de la misma prenda dejarían de ser comparables.
    """
    caja = mascara.convert("L").point(lambda v: 255 if v > 127 else 0).getbbox()
    return caja if caja is not None else (0, 0, mascara.width, mascara.height)


#: El ligamento, deducido del nombre comercial.
#:
#: NO es un adorno: es el dato que más determina el aspecto de un tejido. Un
#: tafetán y un punto del mismo color y el mismo gramaje no se parecen en nada
#: —uno es liso y rígido con brillo seco, el otro es mate y con malla— y la
#: diferencia entre los dos está en esta palabra y en ninguna otra de la ficha.
#:
#: El catálogo está en español y el modelo entiende mejor el inglés, así que la
#: traducción tiene que ocurrir en algún sitio. Aquí, con un diccionario
#: pequeño que cae con elegancia: si el nombre no coincide con nada, se manda
#: la composición y el modelo hace lo que puede.
LIGAMENTOS = {
    "tafetán": "taffeta, with a crisp smooth surface and a dry sheen",
    "tafetan": "taffeta, with a crisp smooth surface and a dry sheen",
    "popelín": "poplin, with a fine flat plain weave",
    "popelin": "poplin, with a fine flat plain weave",
    "lino": "linen, with a visible irregular slubby weave",
    "denim": "denim twill, with a diagonal twill line",
    "franela": "flannel, with a brushed matte fuzzy surface",
    "vichy": "gingham, with an even woven check",
    "punto": "jersey knit, with visible knitted loops",
    "rayas": "yarn-dyed striped jersey",
    "sarga": "twill, with a diagonal rib",
    "seda": "silk, smooth with a soft lustre",
    "lana": "wool, matte with a slight nap",
}

#: Las fibras, del español de la ficha al inglés que entiende el modelo.
FIBRAS = {
    "algodón": "cotton",
    "algodon": "cotton",
    "lino": "linen",
    "seda": "silk",
    "lana virgen": "virgin wool",
    "lana": "wool",
    "elastano": "elastane",
    "poliéster": "polyester",
    "poliester": "polyester",
    "viscosa": "viscose",
}


def _describir(tela) -> str:
    """Cómo se le cuenta la tela al modelo generativo.

    Se construye con la ficha técnica, no con el nombre comercial: «Lino
    Toscana 320» no le dice nada a un modelo.

    LO QUE FALTABA, Y ERA LO QUE MÁS PESABA
    ---------------------------------------
    Esto devolvía «burdeos, 100% seda, lightweight and fluid fabric». Tres
    problemas: mezclaba los dos idiomas, **no decía el ligamento** —que es lo
    que distingue un tafetán de un satén de la misma seda— y no daba el color
    exacto, aunque la ficha lo tiene en hexadecimal.

    El color en hexadecimal importa de verdad aquí: el cliente pide la tela por
    su referencia, y una imagen que le enseñe otro burdeos es una imagen que
    miente sobre el producto.
    """
    nombre = tela.name.lower()
    partes: list[str] = []

    if tela.color_name:
        partes.append(tela.color_name.lower())
    if tela.color_hex:
        partes.append(f"(exactly colour {tela.color_hex})")

    ligamento = next((v for k, v in LIGAMENTOS.items() if k in nombre), None)

    composicion = (tela.composition or "").lower()
    for español, ingles in FIBRAS.items():
        composicion = composicion.replace(español, ingles)
    if composicion:
        partes.append(composicion)

    if ligamento:
        partes.append(ligamento)
    elif not composicion:
        partes.append(nombre)

    dibujo = {
        "stripes": "with woven stripes",
        "checks": "with a woven check pattern",
        "print": "with a printed pattern",
        "textured": "with a pronounced surface texture",
    }.get(tela.pattern.value)
    if dibujo:
        partes.append(dibujo)

    if tela.weight_gsm:
        partes.append(
            f"{tela.weight_gsm} g/m², "
            + ("lightweight and fluid" if tela.weight_gsm < 150 else "heavy and structured")
        )

    return ", ".join(partes) + " fabric"
