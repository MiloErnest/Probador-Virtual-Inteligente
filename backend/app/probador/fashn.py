"""FASHN VTON 1.5, a través de su Space gratuito en Hugging Face.

POR QUÉ ESTE MODELO
-------------------
Se compararon los modelos abiertos de prueba virtual que tenían una demo
funcionando. De los que respondían, FASHN VTON 1.5 (2026) es el único con
licencia libre (Apache 2.0; IDM-VTON y CatVTON son no comerciales), está hecho
para conservar a la persona y genera en el espacio de píxeles, sin el
autocodificador que emborrona los estampados. Acepta la prenda como foto de
producto.

Medido con dos fotos reales y dos prendas del taller: una persona sentada con
la camiseta de rayas azul rey, y otra haciéndose una foto en un espejo con la
camiseta de palmeras. Las dos veces colocó la prenda con su dibujo y su color,
siguiendo la postura, en unos 28 s.

SE LE PIDE QUE BORRE LA PRENDA VIEJA ANTES DE PINTAR
----------------------------------------------------
FASHN tiene dos modos. El que trae por defecto no borra nada («sin máscara»);
el otro borra primero la ropa de la categoría con su propio analizador. Se usa
el segundo, y por una prueba real del usuario: una foto frente al espejo con
el brazo levantado sujetando el móvil y una camiseta negra. Sin borrar, el
modelo dejó un trozo de la manga negra en el hombro, bajo el brazo. Borrando,
desapareció. En las otras dos fotos de prueba los dos modos salen parecidos,
y borrando tardó 13 s en dos de las tres llamadas, frente a 28 s.

Lo que el modo de borrar tiene de malo —redibuja más, manos incluidas— no
llega al resultado: `conservar.py` solo toma del modelo la ropa.

LO QUE CUESTA: NADA, PERO CON CUOTA
-----------------------------------
El Space corre en ZeroGPU, que Hugging Face presta gratis con una cuota diaria
por usuario. Sin identificarse se agota en DOS pruebas (medido: el tercer
intento devolvió «You have exceeded your ZeroGPU runs limit»). Con una cuenta
gratuita y su token en `HF_TOKEN`, la cuota es mayor. Ningún error de cuota se
convierte en un fallo misterioso: se traduce a qué hacer.

LOS 502 DE HUGGING FACE SE REINTENTAN, PERO NUNCA EL MODELO
------------------------------------------------------------
La pasarela de Hugging Face devuelve de vez en cuando un «502 Bad Gateway»,
sobre todo mientras el Space se reinicia. Le pasó al usuario dos veces
seguidas: una al conectar, y otra —peor— al DESCARGAR el resultado, cuando el
modelo ya había generado la imagen y gastado cuota. Esa imagen se perdía.

Ahora se reintentan la conexión y la descarga, que no gastan cuota. La
descarga la hace este módulo y no el cliente de Gradio, precisamente para
poder repetirla sin volver a llamar al modelo. Lo que NO se reintenta nunca
es la generación: si falla, puede haber gastado cuota, y repetirla a ciegas
podría gastarla dos veces.

LA FOTO SALE DE ESTE SERVIDOR
-----------------------------
Hacia un Space público de Hugging Face que mantiene FASHN AI. La interfaz lo
dice antes de subir la foto. El resultado se trae y se guarda aquí; lo que el
Space haga con sus archivos temporales no depende de este proyecto.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import httpx
from PIL import Image

from app.core.config import settings
from app.models.try_on import GarmentCategory
from app.probador.proveedor import PeticionDePrueba
from app.textil.errores import ErrorDeMotor

CATEGORIAS = {
    GarmentCategory.TOP: "tops",
    GarmentCategory.BOTTOM: "bottoms",
    GarmentCategory.FULL: "one-pieces",
}

#: Lado mayor con el que se manda la persona. El modelo trabaja a 864 px de
#: alto, así que mandar más solo alarga la subida.
LADO_DE_ENVIO = 1280

#: Base de la semilla; se le suma el número de la prueba.
SEMILLA = 42

#: Esperas entre intentos, en segundos, al conectar y al descargar el
#: resultado. Tres intentos más en unos 17 s: lo que suele durar un 502 de la
#: pasarela mientras el Space se reinicia.
ESPERAS = (2.0, 5.0, 10.0)


class ModeloFashn:
    nombre = "fashn-vton-1.5"

    def vestir(self, peticion: PeticionDePrueba) -> Image.Image:
        from gradio_client import Client, handle_file

        with tempfile.TemporaryDirectory() as carpeta:
            carpeta = Path(carpeta)
            persona = peticion.persona.convert("RGB")
            persona.thumbnail((LADO_DE_ENVIO, LADO_DE_ENVIO), Image.Resampling.LANCZOS)
            ruta_persona = carpeta / "persona.jpg"
            persona.save(ruta_persona, quality=95)
            ruta_prenda = carpeta / "prenda.png"
            peticion.prenda.convert("RGB").save(ruta_prenda)

            cliente = _conectar(Client)

            trabajo = cliente.submit(
                person_image=handle_file(str(ruta_persona)),
                garment_image=handle_file(str(ruta_prenda)),
                category=CATEGORIAS[peticion.categoria],
                garment_photo_type="flat-lay",
                num_timesteps=settings.VTO_STEPS,
                guidance_scale=1.5,
                # Una semilla por prueba. Ver `PeticionDePrueba.variante`.
                seed=SEMILLA + peticion.variante,
                # Borrar la prenda vieja antes de pintar. Ver la cabecera.
                segmentation_free=False,
                api_name="/try_on",
            )
            try:
                salida = trabajo.result(timeout=settings.VTO_TIMEOUT_SECONDS)
            except TimeoutError as exc:
                trabajo.cancel()
                raise ErrorDeMotor(
                    f"El modelo de prueba virtual no ha respondido en "
                    f"{settings.VTO_TIMEOUT_SECONDS} s. Suele ser cola en Hugging Face; "
                    "vuelve a intentarlo más tarde."
                ) from exc
            except Exception as exc:  # noqa: BLE001
                raise ErrorDeMotor(traducir_error(str(exc))) from exc

            ruta = _descargar(cliente, salida, carpeta)
            try:
                imagen = Image.open(ruta)
                imagen.load()
            except Exception as exc:  # noqa: BLE001
                raise ErrorDeMotor("El modelo de prueba virtual no ha devuelto una imagen.") from exc
            return imagen.convert("RGB")


def _conectar(Client):
    """El cliente del Space, con reintentos: conectar no gasta cuota."""
    ultimo: Exception | None = None
    for espera in (0.0, *ESPERAS):
        time.sleep(espera)
        try:
            return Client(
                settings.VTO_SPACE,
                token=settings.HF_TOKEN or None,
                verbose=False,
                # El resultado lo descarga `_descargar`, que sabe reintentarlo.
                download_files=False,
                httpx_kwargs={"timeout": 60},
                # Sin telemetría: no hace falta, y es una conexión más hacia
                # fuera con cada prueba.
                analytics_enabled=False,
            )
        except Exception as exc:  # noqa: BLE001
            ultimo = exc
    raise ErrorDeMotor(
        "No se ha podido conectar con el modelo de prueba virtual en Hugging Face "
        f"({settings.VTO_SPACE}) tras cuatro intentos. Puede estar arrancando o caído; "
        "vuelve a intentarlo en un par de minutos."
    ) from ultimo


def _descargar(cliente, salida, carpeta: Path) -> Path:
    """Trae la imagen generada, reintentando los fallos del servidor.

    Aquí la imagen YA existe y ya se ha pagado su cuota: perderla por un 502
    de la pasarela sería tirarla. Un 4xx no se reintenta —el archivo no está, y
    no va a aparecer—; un 5xx o un corte de red, sí.
    """
    from gradio_client import utils

    datos = salida if isinstance(salida, dict) else {"path": getattr(salida, "path", salida)}
    url = datos.get("url") or ""
    if not url.startswith(("http://", "https://")):
        url = cliente.src_prefixed + "file=" + utils.encode_file_path(datos["path"])
    destino = carpeta / "resultado"

    ultimo: Exception | None = None
    for espera in (0.0, *ESPERAS):
        time.sleep(espera)
        try:
            with httpx.stream(
                "GET", url, headers=cliente.headers, follow_redirects=True, timeout=60
            ) as respuesta:
                respuesta.raise_for_status()
                with open(destino, "wb") as archivo:
                    for trozo in respuesta.iter_bytes():
                        archivo.write(trozo)
            return destino
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code < 500:
                raise ErrorDeMotor(
                    "El modelo ha generado la imagen, pero Hugging Face ya no la tiene "
                    f"(error {exc.response.status_code}). Vuelve a intentarlo."
                ) from exc
            ultimo = exc
        except httpx.TransportError as exc:
            ultimo = exc
    raise ErrorDeMotor(
        "El modelo ha generado la imagen, pero Hugging Face ha fallado cuatro veces al "
        "devolverla (su pasarela, no tu foto ni la prenda). Vuelve a intentarlo en un "
        "par de minutos."
    ) from ultimo


def traducir_error(mensaje: str) -> str:
    """Del error del Space a algo que se pueda hacer."""
    texto = mensaje.lower()
    if "zerogpu" in texto or "quota" in texto or "runs limit" in texto:
        if settings.HF_TOKEN:
            return (
                "Se ha agotado la cuota diaria gratuita de Hugging Face de tu cuenta. "
                "Se renueva a las 24 horas del primer uso."
            )
        return (
            "Se ha agotado la cuota gratuita de Hugging Face para hoy: sin cuenta son "
            "unas dos pruebas al día. Con una cuenta gratuita hay más: crea un token "
            "de lectura en huggingface.co/settings/tokens y ponlo como HF_TOKEN en "
            "backend/.env."
        )
    if "queue" in texto and "full" in texto:
        return "El modelo de prueba virtual tiene la cola llena. Vuelve a intentarlo en unos minutos."
    if "502" in texto or "503" in texto or "bad gateway" in texto or "unavailable" in texto:
        return (
            "Hugging Face ha tenido un fallo momentáneo en su pasarela (no es tu foto "
            "ni la prenda). Vuelve a intentarlo en un par de minutos."
        )
    if "sleeping" in texto or "building" in texto or "starting" in texto:
        return "El modelo de prueba virtual se está arrancando. Vuelve a intentarlo en un par de minutos."
    corto = mensaje.strip().splitlines()[0][:200] if mensaje.strip() else "sin detalle"
    return f"El modelo de prueba virtual ha fallado: {corto}"
