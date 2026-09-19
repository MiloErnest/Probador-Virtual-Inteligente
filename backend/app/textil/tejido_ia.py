"""Sintetizar el MOSAICO de una tela con IA. No la prenda: la tela.

POR QUÉ ESTE MÓDULO EXISTE
--------------------------
Porque el problema estaba mal planteado, y la documentación de OpenAI lo dice
sin rodeos: *«masking with GPT Image is entirely prompt-based»* y el modelo
*«may not follow mask shapes with complete precision»*. No hay parámetro de
intensidad, ni de ruido, ni condicionamiento estructural. **La máscara es una
sugerencia.**

Con eso sobre la mesa, pedirle a un modelo generativo que conserve la geometría
de una prenda no es un problema de prompt: es pedirle una garantía que la API no
ofrece. Se midió cinco veces, con los dos modelos, con `input_fidelity="high"` y
dándole ya hecha la imagen correcta. Las cinco devolvió otra prenda.

LA SOLUCIÓN NO ES OTRO PROMPT: ES SACAR AL MODELO DEL CAMINO DE LA GEOMETRÍA
----------------------------------------------------------------------------
La geometría —silueta, pliegues, costuras, detalles, la persona— sale del
retexturizado determinista, que es una multiplicación por píxel y por
construcción **no puede mover nada**. Lo que le falta a ese camino no es
geometría: es que el mosaico parezca tela de verdad y no un dibujo procedural.

Eso sí sabe hacerlo un modelo generativo, y ahí no hay nada que conservar. Un
trozo de tela plano no tiene diseño que respetar.

    ficha de la tela + mosaico procedural
        --> IA --> mosaico fotográfico (una vez, y se guarda)
        --> retexturizado determinista --> resultado, con la geometría exacta

SE PAGA UNA VEZ POR TELA, NO UNA POR PRUEBA
-------------------------------------------
Y eso cambia el modelo de coste por completo: doce telas son doce llamadas para
siempre, en vez de una por cada comparación que haga cada usuario. Además
conserva lo que hace útil comparar: la misma tela da siempre el mismo mosaico, y
entre dos pruebas lo único que cambia sigue siendo la tela.

SE EDITA EL MOSAICO PROCEDURAL, NO SE GENERA DE CERO
----------------------------------------------------
Partir del mosaico que ya existe ancla el color —que viene de la ficha técnica y
tiene que coincidir con el rollo real— y la escala del ligamento. Generar de
cero deja las dos cosas al azar, y el color de una tela no es un detalle
estético: es la referencia por la que el cliente la pide.
"""

from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image

from app.core.config import settings
from app.textil.errores import ErrorDeMotor

#: Lado del mosaico que se pide y se guarda.
LADO = 1024

#: Anchura de la zona de fundido al hacerlo repetible, en fracción del lado.
#:
#: El mosaico se repite con envoltura (`np.mod`), así que si sus bordes no
#: encajan aparece una rejilla. Un modelo generativo no devuelve bordes que
#: encajen —no sabe que va a repetirse— y pedírselo por escrito no funciona.
#: Se arregla después y se arregla exacto.
FUNDIDO = 0.25


def sintetizar_mosaico(
    descripcion: str, mosaico: Image.Image | None = None
) -> tuple[Image.Image, int | None]:
    """Devuelve un mosaico fotográfico de la tela, y los tokens que costó.

    `descripcion` sale de la ficha técnica: color, composición, gramaje. Es lo
    que distingue un popelín de 120 g de una franela de 320.
    """
    if not settings.OPENAI_API_KEY:
        raise ErrorDeMotor(
            "Falta OPENAI_API_KEY en backend/.env. Se obtiene en "
            "platform.openai.com/api-keys."
        )

    import openai
    from openai import OpenAI

    cliente = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=settings.OPENAI_TIMEOUT_SECONDS,
        max_retries=0,
    )

    peticion = {
        "model": settings.OPENAI_TEXTURE_MODEL,
        "prompt": _instruccion(descripcion),
        "size": f"{LADO}x{LADO}",
        "quality": settings.OPENAI_TEXTURE_QUALITY,
        "n": 1,
    }

    try:
        if mosaico is not None:
            partida = mosaico.convert("RGB").resize((LADO, LADO), Image.Resampling.LANCZOS)
            peticion["image"] = ("tela.png", _a_png(partida), "image/png")
            respuesta = _editar(cliente, peticion)
        else:
            respuesta = cliente.images.generate(**peticion)
    except openai.AuthenticationError as exc:
        raise ErrorDeMotor("OpenAI ha rechazado la clave.") from exc
    except openai.RateLimitError as exc:
        raise ErrorDeMotor(
            "OpenAI ha rechazado la petición por cuota: normalmente es falta de saldo."
        ) from exc
    except openai.BadRequestError as exc:
        raise ErrorDeMotor(f"OpenAI ha rechazado la petición: {exc}") from exc
    except openai.APIConnectionError as exc:
        raise ErrorDeMotor("No se ha podido conectar con OpenAI.") from exc

    datos = respuesta.data[0] if respuesta.data else None
    if datos is None or not datos.b64_json:
        raise ErrorDeMotor("OpenAI ha respondido sin imagen.")

    imagen = Image.open(io.BytesIO(base64.b64decode(datos.b64_json))).convert("RGB")
    tokens = respuesta.usage.total_tokens if respuesta.usage else None
    return hacer_repetible(imagen), tokens


def _editar(cliente, peticion: dict):
    """Llama a `images.edit` pidiendo la máxima fidelidad que acepte el modelo.

    `input_fidelity` no lo admiten todos. Un 400 por ese motivo se rechaza
    ANTES de generar imagen, así que reintentar sin él no cuesta nada — y la
    alternativa, una lista de qué modelo admite qué, caduca con el siguiente.
    """
    import openai

    try:
        return cliente.images.edit(**peticion, input_fidelity=settings.OPENAI_INPUT_FIDELITY)
    except openai.BadRequestError as exc:
        if "input_fidelity" not in str(exc):
            raise
        return cliente.images.edit(**peticion)


def hacer_repetible(imagen: Image.Image) -> Image.Image:
    """Convierte cualquier imagen en un mosaico que se repite sin junta.

    CÓMO
    ----
    Se funde la imagen consigo misma desplazada media anchura y media altura,
    con una rampa suave. Lo que antes era el borde queda en el centro del
    fundido, y el nuevo borde es el centro de la imagen original — que encaja
    consigo mismo por construcción.

    Cuesta algo de nitidez en las zonas fundidas y a cambio la junta desaparece
    del todo. En un tejido, que es una textura estadística y no un dibujo con
    composición, el intercambio sale muy a favor.
    """
    lado = min(imagen.size)
    recorte = imagen.convert("RGB").crop((0, 0, lado, lado)).resize(
        (LADO, LADO), Image.Resampling.LANCZOS
    )
    px = np.asarray(recorte, dtype=np.float32) / 255.0

    desplazada = np.roll(px, (LADO // 2, LADO // 2), axis=(0, 1))

    banda = max(2, round(LADO * FUNDIDO))
    rampa = np.zeros(LADO, dtype=np.float32)
    t = np.linspace(0.0, 1.0, banda, dtype=np.float32)
    # Suavizado de Hermite: llega a los extremos con pendiente cero, así que el
    # fundido no deja una arista visible donde empieza.
    suave = t * t * (3.0 - 2.0 * t)
    rampa[:banda] = suave
    rampa[banda:-banda] = 1.0
    rampa[-banda:] = suave[::-1]

    peso = np.minimum(rampa[:, None], rampa[None, :])[..., None]
    mezcla = px * peso + desplazada * (1.0 - peso)

    return Image.fromarray(np.clip(mezcla * 255.0, 0, 255).astype(np.uint8), mode="RGB")


def medir_junta(mosaico: Image.Image) -> float:
    """Cuánto se nota la unión al repetir, de 0 a 1.

    Es la comprobación objetiva de que `hacer_repetible` hizo su trabajo: se
    compara el salto entre columnas opuestas del mosaico con el salto medio
    entre columnas vecinas de dentro. Un mosaico repetible da ~1; uno con junta,
    mucho más.
    """
    px = np.asarray(mosaico.convert("RGB"), dtype=np.float32) / 255.0
    salto_junta = float(np.abs(px[:, 0] - px[:, -1]).mean())
    salto_interior = float(np.abs(px[:, 1:] - px[:, :-1]).mean()) or 1e-6
    return salto_junta / salto_interior


def _instruccion(descripcion: str) -> str:
    """Lo que se le pide al modelo.

    En inglés, como el resto: estos modelos siguen instrucciones en inglés con
    más precisión. Y lo que se pide es MUY concreto — un trozo de tela plano y
    de frente— porque cualquier cosa que insinúe una prenda le invita a dibujar
    una, y aquí no queremos prendas.
    """
    return (
        f"A flat, top-down macro photograph of a piece of {descripcion}. "
        "Fill the entire frame with the fabric surface, perfectly flat and "
        "parallel to the camera, as a textile swatch photographed for a catalogue. "
        "Show the real weave: individual threads, the grain, the natural micro "
        "texture and fibre of the material. "
        "Even, diffuse, shadowless lighting. Keep the exact same colour and the "
        "same pattern scale as the input. "
        "No garment, no clothing, no seams, no folds, no wrinkles, no draping, "
        "no hands, no mannequin, no background, no props, no text, no watermark. "
        "Just the fabric surface, edge to edge."
    )


def _a_png(imagen: Image.Image) -> bytes:
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    return buffer.getvalue()
