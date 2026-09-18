"""Motor generativo con la API de OpenAI.

CUÁNDO ES LA HERRAMIENTA CORRECTA
---------------------------------
Con un BOCETO. Un dibujo de líneas no tiene sombras, así que no hay luz que
reutilizar: el volumen, la caída y el brillo de la tela hay que inventarlos, y
eso es exactamente lo que un modelo generativo sabe hacer.

Con una FOTOGRAFÍA es la opción peor casi siempre, y conviene saber por qué
antes de usarla: cuesta dinero, tarda segundos en vez de milisegundos, y **no
es determinista**. Dos llamadas idénticas dan dos imágenes distintas. En un
producto cuya promesa es «compara cuatro telas sobre TU diseño», un motor que
redibuja el diseño en cada llamada está haciendo lo contrario de lo que se le
pide.

`input_fidelity="high"` existe justo para esto y ayuda mucho, pero ayuda: no
garantiza. La foto tiene su propia luz y reutilizarla es gratis y exacto.

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

        tamano = _tamano_para(peticion.prenda.size)
        ancho, alto = (int(v) for v in tamano.split("x"))

        # La imagen y la máscara tienen que medir lo mismo y salir en PNG.
        prenda = peticion.prenda.convert("RGB").resize((ancho, alto), Image.Resampling.LANCZOS)
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
            "prompt": _instruccion(peticion),
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

        tokens = respuesta.usage.total_tokens if respuesta.usage else None
        return ResultadoDeTela(imagen=imagen, proveedor=self.nombre, tokens=tokens)


def _instruccion(peticion: PeticionDeTela) -> str:
    """El texto que se le da al modelo.

    Está en inglés a propósito: estos modelos siguen instrucciones en inglés
    con bastante más precisión, y aquí lo que se le pide es sobre todo lo que
    NO debe tocar.

    La mitad del texto son prohibiciones, y no sobran. Sin ellas el modelo
    «mejora» el diseño: mueve los botones, cambia el cuello, endereza el corte.
    Para una modista que quiere ver SU prenda con otra tela, eso lo invalida.
    """
    tela = peticion.descripcion

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
