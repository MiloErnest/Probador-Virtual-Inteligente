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

LA FOTO SALE DE ESTE SERVIDOR
-----------------------------
Hacia un Space público de Hugging Face que mantiene FASHN AI. La interfaz lo
dice antes de subir la foto. El resultado se trae y se guarda aquí; lo que el
Space haga con sus archivos temporales no depende de este proyecto.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

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

            try:
                cliente = Client(
                    settings.VTO_SPACE,
                    token=settings.HF_TOKEN or None,
                    verbose=False,
                    download_files=str(carpeta),
                    httpx_kwargs={"timeout": 60},
                    # Sin telemetría: no hace falta, y es una conexión más
                    # hacia fuera con cada prueba.
                    analytics_enabled=False,
                )
            except Exception as exc:  # noqa: BLE001
                raise ErrorDeMotor(
                    "No se ha podido conectar con el modelo de prueba virtual en Hugging "
                    f"Face ({settings.VTO_SPACE}). Puede estar arrancando o caído; "
                    "vuelve a intentarlo en un par de minutos."
                ) from exc

            trabajo = cliente.submit(
                person_image=handle_file(str(ruta_persona)),
                garment_image=handle_file(str(ruta_prenda)),
                category=CATEGORIAS[peticion.categoria],
                garment_photo_type="flat-lay",
                num_timesteps=settings.VTO_STEPS,
                guidance_scale=1.5,
                # Semilla fija: la misma foto con la misma prenda da siempre lo
                # mismo, y dos prendas sobre la misma foto son comparables.
                seed=42,
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

            ruta = salida.get("path") if isinstance(salida, dict) else salida
            try:
                imagen = Image.open(ruta)
                imagen.load()
            except Exception as exc:  # noqa: BLE001
                raise ErrorDeMotor("El modelo de prueba virtual no ha devuelto una imagen.") from exc
            return imagen.convert("RGB")


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
    if "sleeping" in texto or "building" in texto or "starting" in texto:
        return "El modelo de prueba virtual se está arrancando. Vuelve a intentarlo en un par de minutos."
    corto = mensaje.strip().splitlines()[0][:200] if mensaje.strip() else "sin detalle"
    return f"El modelo de prueba virtual ha fallado: {corto}"
