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

#: Lado máximo que se le pide a la API. Se cobra por píxel, así que esto es el
#: techo de gasto por llamada; por debajo, manda el tamaño propio de la prenda.
LADO_MAXIMO = 1536


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

        ancho, alto = _tamano_para(peticion.prenda.size)
        tamano = f"{ancho}x{alto}"

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

        # LA TELA SE LE ENSEÑA, NO SE LE CUENTA.
        #
        # Hasta ahora la tela viajaba solo como texto —«burdeos, 100% seda»— y
        # el modelo tenía que imaginársela. Imaginarse el material y
        # imaginarse la prenda son, para un modelo generativo, el mismo acto.
        #
        # La API acepta hasta 16 imágenes y aplica la máscara SOBRE LA PRIMERA,
        # así que la prenda va primera y el mosaico detrás, como referencia.
        imagenes = [("prenda.png", _a_png(prenda), "image/png")]
        if peticion.mosaico is not None:
            muestra = peticion.mosaico.convert("RGB").resize(
                (512, 512), Image.Resampling.LANCZOS
            )
            imagenes.append(("tela.png", _a_png(muestra), "image/png"))

        peticion_api = {
            "model": settings.OPENAI_IMAGE_MODEL,
            "image": imagenes if len(imagenes) > 1 else imagenes[0],
            "mask": ("mascara.png", _a_png(mascara), "image/png"),
            "prompt": _instruccion(peticion, desde_retexturizado, len(imagenes) > 1),
            "size": tamano,
            "quality": settings.OPENAI_IMAGE_QUALITY,
            "n": 1,
        }

        try:
            try:
                respuesta = _llamar(cliente, peticion_api)
            except openai.BadRequestError as exc:
                # EL TAMAÑO NATIVO NO LO ADMITEN TODOS LOS MODELOS.
                #
                # La documentación dice que `size` acepta cualquier múltiplo de
                # 16; la API dice que depende del modelo — `gpt-image-1-mini`
                # responde 400 con «Supported sizes are 1024x1024, 1024x1536,
                # 1536x1024, and auto». Se descubrió llamando, que es la única
                # forma. Mismo trato que `input_fidelity`: el 400 se rechaza
                # antes de generar nada, así que reintentar es gratis, y una
                # tabla de qué modelo admite qué caducaría con el siguiente.
                if "size" not in str(exc).lower():
                    raise
                peticion_api["size"] = _tamano_de_catalogo(peticion.prenda.size)
                respuesta = _llamar(cliente, peticion_api)

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


def _llamar(cliente, peticion: dict):
    """Llama a `images.edit` con la máxima fidelidad que acepte el modelo.

    EL ÚNICO REINTENTO DE TODO EL PROYECTO, Y ES GRATIS
    ---------------------------------------------------
    `input_fidelity` no lo admiten todos los modelos: `gpt-image-1-mini` lo
    rechaza con un 400. Reintentar aquí no contradice la regla de «sin
    reintentos automáticos», que existe para no repetir algo que se cobra: un
    400 se rechaza ANTES de generar ninguna imagen.

    **Y conviene saber lo que significa que se dispare.** Durante todas las
    pruebas del proyecto el modelo configurado era el mini, así que este camino
    se tomaba SIEMPRE: cada llamada salía con la fidelidad desactivada sin que
    se notara en ninguna parte. Eso explica buena parte de por qué el modelo
    reinterpretaba el diseño, y es la razón de que ahora el modelo por defecto
    sea uno que sí la admite.
    """
    import openai

    try:
        return cliente.images.edit(**peticion, input_fidelity=settings.OPENAI_INPUT_FIDELITY)
    except openai.BadRequestError as exc:
        if "input_fidelity" not in str(exc):
            raise
        return cliente.images.edit(**peticion)


def _tamano_de_catalogo(tamano: tuple[int, int]) -> str:
    """Los tres tamaños fijos, para los modelos que no admiten otra cosa."""
    ancho, alto = tamano
    proporcion = ancho / max(1, alto)
    if proporcion > 1.2:
        return "1536x1024"
    if proporcion < 0.83:
        return "1024x1536"
    return "1024x1024"


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


def _instruccion(
    peticion: PeticionDeTela, desde_retexturizado: bool, con_muestra: bool = False
) -> str:
    """El texto que se le da al modelo.

    Está en inglés a propósito: estos modelos siguen instrucciones en inglés
    con bastante más precisión, y aquí lo que se le pide es sobre todo lo que
    NO debe tocar.

    La mitad del texto son prohibiciones, y no sobran. Sin ellas el modelo
    «mejora» el diseño: mueve los botones, cambia el cuello, endereza el corte.
    Para una modista que quiere ver SU prenda con otra tela, eso lo invalida.
    """
    tela = peticion.descripcion

    # Cuando va una segunda imagen hay que decirle QUÉ es, o intentará fundir
    # las dos: la segunda no es una prenda ni una escena, es solo el material.
    muestra = (
        "The SECOND image is not a garment and not a scene: it is a flat swatch "
        "of the fabric, provided only as the material reference. Use its weave, "
        "its colour and its surface, and nothing else from it. "
        if con_muestra
        else ""
    )

    if desde_retexturizado:
        # La tela YA está puesta. Pedirle que la ponga otra vez sería invitarle
        # a rehacer la prenda, que es justo lo que no queremos.
        return (
            muestra
            + f"The FIRST image already shows the correct garment with the correct "
            f"fabric ({tela}) applied. Your ONLY task is to make that fabric look like a real "
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


def _tamano_para(tamano: tuple[int, int]) -> tuple[int, int]:
    """El tamaño que se le pide a la API, lo más cerca posible del original.

    ANTES SE FORZABA A TRES TAMAÑOS FIJOS, Y ESO ERA UN DEFECTO
    ----------------------------------------------------------
    Se llevaba todo a 1024x1024, 1536x1024 o 1024x1536. Una prenda de 794x1111
    se ampliaba a 1024x1536 y el resultado se devolvía a 794x1111: **dos
    remuestreos completos de la geometría** para nada. La textura fina —el
    grano de la tela, el pespunte— no sobrevive a ese viaje.

    La API acepta hoy cualquier tamaño múltiplo de 16 entre 1:3 y 3:1. Así que
    se manda el tamaño propio de la prenda, ajustado al múltiplo de 16 más
    cercano y limitado por arriba para no disparar el coste, que se cobra por
    píxel.
    """
    ancho, alto = tamano
    proporcion = ancho / max(1, alto)

    # Fuera del rango que admite la API, se recorta la proporción.
    if proporcion > 3.0:
        alto = round(ancho / 3.0)
    elif proporcion < 1 / 3:
        ancho = round(alto / 3.0)

    escala = min(1.0, LADO_MAXIMO / max(ancho, alto))
    ancho = max(256, round(ancho * escala))
    alto = max(256, round(alto * escala))

    # Múltiplo de 16, que es lo que exige la API.
    return (round(ancho / 16) * 16, round(alto / 16) * 16)


def _mascara_invertida(mascara: Image.Image, tamano: tuple[int, int]) -> Image.Image:
    """Convierte nuestra máscara en la que espera la API.

    Nosotros: 255 = prenda. La API: transparente = lo que hay que cambiar.
    Así que la prenda tiene que quedar TRANSPARENTE.

    Y BINARIA, QUE ES LO QUE ESTABA MAL
    -----------------------------------
    Nuestra máscara lleva difuminado de borde —medido, entre 13 y 25 px de
    ancho, un 3% de los píxeles— porque lo necesita para componer sin que se
    vea el empalme. Pero la API define UN solo caso: *«fully transparent areas
    (where alpha is zero) indicate where image should be edited»*. Lo que valga
    128 no está definido, y lo que no está definido pasa justo en el contorno,
    que es donde más duele.

    Así que aquí se manda binaria y el difuminado se queda para la composición
    nuestra, que es donde sí significa algo.
    """
    gris = mascara.convert("L").resize(tamano, Image.Resampling.BILINEAR)
    dura = gris.point(lambda v: 0 if v >= 128 else 255)

    lienzo = Image.new("RGBA", tamano, (0, 0, 0, 0))
    lienzo.putalpha(dura)
    return lienzo


def _a_png(imagen: Image.Image) -> bytes:
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    return buffer.getvalue()
