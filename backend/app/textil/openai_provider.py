"""Motor generativo con la API de OpenAI.

QUÉ SE LE MANDA AL MODELO, Y POR QUÉ ES LA DECISIÓN QUE MÁS PESA
----------------------------------------------------------------
No el original: **el retexturizado**. Es decir, una imagen que ya tiene el
diseño del usuario y ya tiene la tela puesta, y al modelo solo se le pide que
la haga fotográfica.

La primera versión mandaba el boceto crudo y pedía «un vestido de tafetán». A
eso el modelo solo puede responder inventándose un vestido, y se lo inventa: el
usuario lo describió exactamente así —«devuelve un vestido, sí, pero totalmente
diferente, hasta le pone botones a las prendas que no llevan»—. No era un fallo
del modelo. Era la pregunta equivocada.

Mandarle la tela ya puesta cambia la tarea de *inventar* a *pulir*, que es
mucho más pequeña, y lo que se le pide deja de competir con lo que el usuario
dibujó.

**Ayuda, y no basta.** Medido con el vestido de noche: con `gpt-image-1-mini`
(3.276 tokens, 24 s) y con `gpt-image-1` + `input_fidelity="high"` (12.987
tokens, 52 s), partiendo de un retexturizado correcto, los dos devolvieron el
vestido con manga larga y cuello barco donde el boceto tiene palabra de honor y
drapeado cruzado. La seda está espléndida; el vestido no es el suyo.

Lo que SÍ garantiza esto es todo lo de fuera de la prenda —fondo, cara, pelo—,
que viene del original y no lo ha tocado nadie.

Y ADEMÁS SE COMPONE A TRAVÉS DE LA MÁSCARA
------------------------------------------
`images.edit` **no** es un parcheo: regenera la imagen entera, también lo que
cae fuera de la máscara. Por eso cambiaba el fondo aunque la máscara estuviera
bien. La salida se recompone contra el original usando nuestra máscara, así que
todo lo que no es prenda queda idéntico al original, píxel a píxel. No es un
apaño: es lo único que garantiza que el modelo no pueda tocar lo que no se le
ha pedido.

`input_fidelity="high"` ayuda con lo de dentro, pero ayuda: no garantiza. Con
una FOTOGRAFÍA el camino determinista sigue siendo mejor casi siempre —es
gratis, instantáneo y **determinista**, y comparar cuatro telas solo significa
algo si lo único que cambia entre las cuatro es la tela.

LA MÁSCARA VA AL REVÉS QUE LA NUESTRA
-------------------------------------
Es el detalle que más cuesta descubrir depurando. En esta API, **lo TRANSPARENTE
de la máscara es lo que se edita**; lo opaco se conserva. Nuestra máscara dice
lo contrario: 255 donde está la prenda.

Así que hay que invertirla. Si se manda tal cual, el modelo respeta la prenda y
reinventa el fondo, que es precisamente el resultado opuesto al que se busca —y
sale una imagen perfectamente plausible, así que no se nota que está mal.

EL COSTE SE REGISTRA
--------------------
La respuesta trae los tokens facturados. Se guardan en la prueba, para que el
gasto sea un número que se pueda sumar y enseñar, y no una preocupación escrita
en un documento.
"""

from __future__ import annotations

import base64
import io

from PIL import Image

from app.core.config import settings
from app.textil.errores import ErrorDeMotor
from app.textil.provider import PeticionDeTela, ResultadoDeTela

#: Tamaños que acepta la API. La prenda se lleva al más parecido a su forma:
#: pedir un cuadrado para una foto apaisada la deformaría.
TAMANOS = {
    "cuadrado": "1024x1024",
    "apaisado": "1536x1024",
    "vertical": "1024x1536",
}


class MotorOpenAI:
    nombre = "openai"

    def aplicar(self, peticion: PeticionDeTela) -> ResultadoDeTela:
        if not settings.OPENAI_API_KEY:
            raise ErrorDeMotor(
                "Falta OPENAI_API_KEY en backend/.env. Se obtiene en "
                "platform.openai.com/api-keys."
            )

        import openai
        from openai import OpenAI

        partida, desde_retexturizado = _punto_de_partida(peticion)

        tamano = _tamano_para(peticion.prenda.size)
        ancho, alto = (int(v) for v in tamano.split("x"))

        # La imagen y la máscara tienen que medir lo mismo y salir en PNG.
        prenda = partida.convert("RGB").resize((ancho, alto), Image.Resampling.LANCZOS)
        mascara = _mascara_invertida(peticion.mascara, (ancho, alto))

        cliente = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.OPENAI_TIMEOUT_SECONDS,
            # Sin reintentos automáticos. Reintentar algo que se cobra por uso
            # vacía una cuenta deprisa y sin avisar; si falla, que lo relance
            # una persona a sabiendas.
            max_retries=0,
        )

        peticion_api = {
            "model": settings.OPENAI_IMAGE_MODEL,
            "image": ("prenda.png", _a_png(prenda), "image/png"),
            "mask": ("mascara.png", _a_png(mascara), "image/png"),
            "prompt": _instruccion(peticion, desde_retexturizado),
            "size": tamano,
            "n": 1,
        }

        try:
            try:
                respuesta = cliente.images.edit(
                    **peticion_api, input_fidelity=settings.OPENAI_INPUT_FIDELITY
                )
            except openai.BadRequestError as exc:
                # EL ÚNICO REINTENTO DE TODO EL PROYECTO, Y ES GRATIS
                # ---------------------------------------------------
                # `input_fidelity` no lo admiten todos los modelos: el mini lo
                # rechaza con un 400. Se descubrió con la primera llamada real,
                # que es la única forma de descubrir estas cosas.
                #
                # Reintentar aquí no contradice la regla de «sin reintentos
                # automáticos», que existe para no repetir algo que se cobra:
                # un 400 se rechaza ANTES de generar ninguna imagen, así que no
                # ha costado nada. Y la alternativa —una lista de qué modelo
                # admite qué— caducaría con el siguiente modelo que saliera.
                if "input_fidelity" not in str(exc):
                    raise
                respuesta = cliente.images.edit(**peticion_api)

        except openai.AuthenticationError as exc:
            raise ErrorDeMotor(
                "OpenAI ha rechazado la clave. Comprueba OPENAI_API_KEY en "
                "backend/.env, o crea otra en platform.openai.com/api-keys."
            ) from exc
        except openai.RateLimitError as exc:
            raise ErrorDeMotor(
                "OpenAI ha rechazado la petición por cuota: normalmente es que la "
                "cuenta no tiene saldo. Añade fondos en Settings → Billing. "
                "(Una clave válida sin saldo falla igual, y el mensaje no lo dice.)"
            ) from exc
        except openai.PermissionDeniedError as exc:
            raise ErrorDeMotor(
                "La clave no tiene permiso para generar imágenes. Al crearla hay que "
                "darle 'Capacidades del modelo' en modo Solicitud."
            ) from exc
        except openai.APITimeoutError as exc:
            raise ErrorDeMotor(
                f"OpenAI ha tardado más de {settings.OPENAI_TIMEOUT_SECONDS} s. "
                "Vuelve a intentarlo."
            ) from exc
        except openai.BadRequestError as exc:
            # Aquí caen el filtro de contenido y los parámetros que el modelo
            # concreto no admite. El mensaje crudo suele ser útil, así que se
            # pasa en vez de esconderlo tras uno genérico.
            raise ErrorDeMotor(f"OpenAI ha rechazado la petición: {exc}") from exc
        except openai.APIConnectionError as exc:
            raise ErrorDeMotor(
                "No se ha podido conectar con OpenAI. Comprueba la conexión."
            ) from exc

        datos = respuesta.data[0] if respuesta.data else None
        if datos is None or not datos.b64_json:
            raise ErrorDeMotor("OpenAI ha respondido sin imagen.")

        imagen = Image.open(io.BytesIO(base64.b64decode(datos.b64_json))).convert("RGB")
        # Se devuelve al tamaño original: el resto de la aplicación —la galería,
        # la comparación lado a lado— cuenta con que todas las pruebas de una
        # misma prenda midan lo mismo.
        if imagen.size != peticion.prenda.size:
            imagen = imagen.resize(peticion.prenda.size, Image.Resampling.LANCZOS)

        imagen = _componer_con_el_original(imagen, peticion.prenda, peticion.mascara)

        tokens = respuesta.usage.total_tokens if respuesta.usage else None
        aviso = (
            "Fuera de la prenda no se ha tocado nada: el fondo y la figura son tu "
            "imagen original. Dentro, el modelo reinterpreta el diseño aunque se le "
            "dé ya hecho — está medido cinco veces, con los dos modelos y con "
            "fidelidad alta. Úsalo para ver la tela como fotografía, y compara "
            "siempre con el original de al lado."
            if desde_retexturizado
            else "Esta tela no tiene mosaico, así que el modelo ha partido de tu "
            "imagen y ha tenido que inventarse la tela entera. Es el caso en el "
            "que más se desvía del diseño."
        )
        return ResultadoDeTela(
            imagen=imagen, proveedor=self.nombre, tokens=tokens, aviso=aviso
        )


def _punto_de_partida(peticion: PeticionDeTela) -> tuple[Image.Image, bool]:
    """Qué imagen se le manda al modelo, y si ya lleva la tela puesta.

    Es la decisión que más cambia el resultado, y no se ve en ningún parámetro.

    Con el mosaico de la tela se puede construir primero el retexturizado: una
    imagen que ya tiene el diseño del usuario Y la tela correcta. Al modelo se
    le pide entonces solo que lo haga fotográfico, que es una tarea pequeña.

    Sin mosaico no hay nada que construir y hay que mandarle el original, con
    la tela descrita en palabras. Ahí el modelo tiene que inventárselo todo, y
    se nota: es el caso en el que más se aleja del diseño. Se avisa.
    """
    if peticion.mosaico is None:
        return peticion.prenda, False

    # Import aquí: `provider` importa este módulo de forma perezosa, así que a
    # la hora de llamar ya está cargado y no hay ciclo.
    from app.textil.provider import MotorRetexturizado

    return MotorRetexturizado().aplicar(peticion).imagen, True


def _componer_con_el_original(
    generada: Image.Image, original: Image.Image, mascara: Image.Image
) -> Image.Image:
    """Devuelve la imagen generada SOLO dentro de la prenda.

    `images.edit` regenera la imagen entera, también lo de fuera de la máscara:
    la máscara le dice dónde centrarse, no dónde tiene prohibido escribir. Por
    eso cambiaba el fondo de un boceto aunque la máscara fuera perfecta.

    Recomponer contra el original es lo único que lo garantiza. Y como la
    máscara lleva su difuminado de borde, el empalme no se ve.
    """
    if mascara.size != original.size:
        mascara = mascara.resize(original.size, Image.Resampling.BILINEAR)
    return Image.composite(generada, original.convert("RGB"), mascara.convert("L"))


def _instruccion(peticion: PeticionDeTela, desde_retexturizado: bool) -> str:
    """El texto que se le da al modelo.

    Está en inglés a propósito: estos modelos siguen instrucciones en inglés
    con bastante más precisión, y aquí lo que se le pide es sobre todo lo que
    NO debe tocar.

    La mitad del texto son prohibiciones, y no sobran. Sin ellas el modelo
    «mejora» el diseño: mueve los botones, cambia el cuello, endereza el corte.
    Para una modista que quiere ver SU prenda con otra tela, eso lo invalida.
    """
    tela = peticion.descripcion

    if desde_retexturizado:
        # La tela YA está puesta. Pedirle que la ponga otra vez sería invitarle
        # a rehacer la prenda, que es justo lo que no queremos.
        return (
            f"This image already shows the correct garment with the correct fabric "
            f"({tela}) applied. Your ONLY task is to make that fabric look like a real "
            "photograph: realistic weave and thread texture, natural sheen, believable "
            "soft shadows inside the folds that are already there. "
            "Keep the garment EXACTLY as it is: every line, seam, edge, hem, neckline, "
            "silhouette and proportion stays in the same place. "
            "Do NOT add buttons, pockets, collars, straps, trims or any element that is "
            "not already visible. Do not remove any. Do not restyle, do not redraw, do "
            "not change the pose, do not change the background. "
            "Think of it as photographing this exact garment, not designing one."
        )

    if peticion.tipo.value == "sketch":
        return (
            f"This is a fashion design sketch. Render the sketched garment as a "
            f"realistic product photograph, made of {tela}. "
            "Keep EXACTLY the same silhouette, proportions, neckline, sleeves, "
            "seams and every design detail drawn in the sketch. "
            "Add realistic fabric folds, drape and soft studio lighting. "
            "Do not redesign, do not add or remove any element, do not change the "
            "cut. Plain neutral background. No people, no mannequin, no text."
        )

    return (
        f"Replace ONLY the fabric of this garment with {tela}. "
        "Keep the exact same garment: identical cut, seams, stitching, buttons, "
        "zippers, collar, pockets, silhouette and proportions. "
        "Keep the same pose, the same lighting, the same shadows and the same "
        "background. Preserve the existing folds and wrinkles of the garment. "
        "Do not restyle, do not redesign, do not move any element. "
        "Photorealistic textile rendering."
    )


def _tamano_para(tamano: tuple[int, int]) -> str:
    ancho, alto = tamano
    proporcion = ancho / max(1, alto)
    if proporcion > 1.2:
        return TAMANOS["apaisado"]
    if proporcion < 0.83:
        return TAMANOS["vertical"]
    return TAMANOS["cuadrado"]


def _mascara_invertida(mascara: Image.Image, tamano: tuple[int, int]) -> Image.Image:
    """Convierte nuestra máscara en la que espera la API.

    Nosotros: 255 = prenda. La API: transparente = lo que hay que cambiar.
    Así que la prenda tiene que quedar TRANSPARENTE.
    """
    gris = mascara.convert("L").resize(tamano, Image.Resampling.BILINEAR)
    alfa = Image.eval(gris, lambda v: 255 - v)

    lienzo = Image.new("RGBA", tamano, (0, 0, 0, 0))
    lienzo.putalpha(alfa)
    return lienzo


def _a_png(imagen: Image.Image) -> bytes:
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    return buffer.getvalue()
