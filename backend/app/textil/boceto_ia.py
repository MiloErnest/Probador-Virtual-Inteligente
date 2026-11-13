"""De un boceto a la fotografía de la prenda. El único sitio donde la IA INVENTA.

POR QUÉ AQUÍ SÍ, CUANDO EN TODO LO DEMÁS NO
-------------------------------------------
En una fotografía la IA no puede tocar la prenda: la forma sale del motor
determinista y el bloqueo estructural descarta lo que el modelo cambie. Eso es
lo correcto cuando la prenda EXISTE, porque inventarla es falsearla.

Un boceto es el caso contrario. La prenda todavía no existe, y lo que el
usuario pide es justo que alguien la imagine cosida. El camino que había
—pintar la tela sobre el dibujo conservando el trazo— era exacto y no servía:
el usuario lo dijo dos veces, primero como «parece que le echara pintura a la
prenda» y después como «un boceto con un color encima, nadie lo quiere».

LO QUE YA SE SABÍA DE ESTE CAMINO, Y POR QUÉ SE PLANTEA DISTINTO
----------------------------------------------------------------
Mandar el boceto crudo al modelo ya se probó en este proyecto y falló: pedía
«un vestido de tafetán» y volvía otro vestido, con botones que nadie dibujó.
Aquella petición mezclaba dos tareas —imaginar la prenda e imaginar la tela—,
iba con un modelo que no admitía `input_fidelity`, y el resultado se usaba tal
cual, una vez por cada tela, sin que nadie lo mirase.

Ahora son tres cosas distintas:

1. **Se le pide una sola tarea.** La prenda del dibujo, sin tela que elegir:
   en su color si el boceto lo trae, y si no en crudo. La tela la pone después
   el motor determinista, que es el que sabe.
2. **Se genera UNA vez por boceto, no una por tela.** Todas las telas se
   prueban sobre la misma prenda, así que entre dos pruebas lo único que
   cambia sigue siendo la tela.
3. **El usuario la ve junto a su boceto antes de usarla**, con una medida de
   cuánto se parece la silueta, y puede pedir otra variante.

Medido con el vestido de noche del usuario (palabra de honor con drapeado
cruzado, falda sirena y sobrefalda con cola), dos veces: las dos salieron con
el escote, el drapeado, el cinturón, la sirena y la cola del dibujo. Unos 3.400
tokens y 37 s cada una.

LO QUE NO SE PUEDE PROMETER
---------------------------
Que sea idéntica. `images.edit` no tiene condicionamiento estructural: recibe
el dibujo y lo interpreta (ver CLAUDE.md, «La causa raíz»). `input_fidelity`
ayuda y no garantiza. Por eso la medida de la silueta y la aprobación: no hay
forma de obligar al modelo, pero sí de no dar por buena una prenda que no es.

EL FONDO ES GRIS, Y LO QUE SE CREYÓ Y NO ERA VERDAD
---------------------------------------------------
La prenda generada pasa por `segmentar_prenda` como una fotografía más. Se pide
sobre gris medio porque una prenda en crudo sobre blanco es el caso que peor
recorta (la camiseta blanca del banco: 0,088 de separación).

La primera prueba salió con dos agujeros en el recorte, de la cintura al bajo,
justo en los pliegues en sombra. Se dio por hecho que el gris de la sombra se
confundía con el gris del fondo, se montó un fondo azul de croma con su cambio
posterior a gris — y la segunda prueba, sobre azul, salió con LOS MISMOS
agujeros. No era el fondo. Era el paso que quita a la figura de un figurín: en
una tela cruda, la sombra de un pliegue es cálida y saturada, y la regla la
tomaba por piel. Sin ese paso (`figura=False`), el recorte sale entero sobre
gris y sobre azul, así que se quedó el gris, que no necesita nada más.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from PIL import Image

from app.core.config import settings
from app.textil.errores import ErrorDeMotor
from app.textil.segmentar import Recorte, segmentar_prenda

#: Lado mayor que se le pide a la API. Se cobra por píxel, pero esta imagen se
#: genera una vez por boceto y sobre ella se prueban todas las telas: es la
#: única llamada del camino, así que se pide con el detalle que admite.
LADO_MAYOR = 1536

#: El gris del fondo, dicho al modelo. No lo clava, y no hace falta: el recorte
#: ajusta el fondo que encuentra, no el que se pidió.
FONDO = "#8C8C8C"

#: Croma (máximo menos mínimo de R, G, B, de 0 a 255) a partir del cual un
#: píxel tiene color. Es el mismo número con el que `segmentar` distingue a la
#: figura del lápiz: el grafito es acromático.
CROMA_DE_COLOR = 18.0

#: Fracción de la prenda que tiene que estar coloreada para tratar el boceto
#: como un boceto a color. Por debajo son retoques —un lazo, un forro— o restos
#: de la figura, y la prenda se hace en crudo.
MINIMO_COLOREADO = 0.30

#: Lado del lienzo en el que se comparan las dos siluetas.
LADO_DE_COMPARACION = 256

#: Por debajo de este parecido de silueta, la prenda no es la del boceto y se
#: avisa.
#:
#: Medido con el vestido de noche del usuario: sus dos prendas generadas, las
#: dos fieles, dan 0,870 y 0,876. Contra siete prendas que no son la suya —las
#: cinco del banco de ejemplo y dos subidas, de un vaquero a una cazadora— da
#: entre 0,42 y 0,57. El umbral va en medio de las dos nubes.
PARECIDO_MINIMO = 0.72


@dataclass(frozen=True)
class PrendaGenerada:
    """La imagen que devuelve el modelo: la prenda sola sobre el fondo gris."""

    imagen: Image.Image
    proveedor: str
    #: Tokens facturados por la llamada.
    tokens: int | None = None


class GeneradorDePrenda(Protocol):
    """Un modelo que convierte un boceto en la fotografía de la prenda."""

    nombre: str

    def generar(self, boceto: Image.Image, *, con_color: bool) -> PrendaGenerada: ...


@dataclass(frozen=True)
class PrendaDeBoceto:
    """Lo que sale de un boceto: la prenda, su recorte y cuánto se le parece."""

    #: La prenda sobre gris. Es la imagen sobre la que se prueban las telas.
    imagen: Image.Image
    recorte: Recorte
    #: Coincidencia de la silueta con la del boceto, de 0 a 1.
    parecido: float
    #: El boceto traía color y se ha respetado; si no, la prenda va en crudo.
    con_color: bool
    proveedor: str
    tokens: int | None


def prenda_desde_boceto(
    boceto: Image.Image, generador: GeneradorDePrenda | None = None
) -> PrendaDeBoceto:
    """El camino entero: del dibujo a una prenda lista para probarle telas."""
    recorte_del_boceto = segmentar_prenda(boceto, boceto=True)
    con_color = boceto_a_color(boceto, recorte_del_boceto.mascara)

    generada = (generador or generador_configurado()).generar(boceto, con_color=con_color)

    recorte = recortar_prenda_generada(generada.imagen)
    return PrendaDeBoceto(
        imagen=generada.imagen,
        recorte=recorte,
        parecido=parecido_de_silueta(recorte_del_boceto.mascara, recorte.mascara),
        con_color=con_color,
        proveedor=generada.proveedor,
        tokens=generada.tokens,
    )


def recortar_prenda_generada(imagen: Image.Image) -> Recorte:
    """El recorte de una prenda generada: como una foto, pero sin buscar figura.

    Vive aquí para que quien tenga que recalcularlo (`scripts/resegmentar`) lo
    haga igual que al generarla. Ver la cabecera: buscar a la figura en una
    prenda cruda le hace dos agujeros.
    """
    return segmentar_prenda(imagen, boceto=False, figura=False)


def generador_configurado() -> GeneradorDePrenda:
    """El generador que toca según `AI_PROVIDER`, o por qué no hay ninguno.

    Mismo trato que `motor_para`: un valor desconocido falla en voz alta. Y sin
    proveedor no hay camino alternativo gratuito al que caer, a propósito: un
    boceto sin generar no se puede probar, y se dice.
    """
    proveedor = settings.AI_PROVIDER.strip().lower()

    if proveedor in ("", "none"):
        raise ErrorDeMotor(
            "Convertir un boceto en prenda necesita el motor de IA, y no está "
            "activado. Pon AI_PROVIDER=openai y tu OPENAI_API_KEY en backend/.env. "
            "Cada boceto generado se cobra."
        )

    if proveedor == "openai":
        return GeneradorOpenAI()

    raise ErrorDeMotor(
        f"AI_PROVIDER='{settings.AI_PROVIDER}' no se reconoce. "
        "Los valores válidos son 'none' y 'openai'."
    )


class GeneradorOpenAI:
    nombre = "openai-boceto"

    def generar(self, boceto: Image.Image, *, con_color: bool) -> PrendaGenerada:
        if not settings.OPENAI_API_KEY:
            raise ErrorDeMotor(
                "Falta OPENAI_API_KEY en backend/.env. Se obtiene en "
                "platform.openai.com/api-keys."
            )

        import openai
        from openai import OpenAI

        # Import aquí: `openai_provider` arrastra el SDK, que tarda en cargar.
        from app.textil.openai_provider import _a_png, _llamar, _tamano_de_catalogo

        ancho, alto = tamano_de_salida(boceto.size)
        dibujo = boceto.convert("RGB").resize((ancho, alto), Image.Resampling.LANCZOS)

        cliente = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.OPENAI_TIMEOUT_SECONDS,
            # Sin reintentos automáticos: cada intento genera y cobra una imagen.
            max_retries=0,
        )

        peticion = {
            "model": settings.OPENAI_IMAGE_MODEL,
            "image": ("boceto.png", _a_png(dibujo), "image/png"),
            "prompt": instruccion(con_color),
            "size": f"{ancho}x{alto}",
            "quality": settings.OPENAI_IMAGE_QUALITY,
            "n": 1,
        }

        try:
            try:
                respuesta = _llamar(cliente, peticion)
            except openai.BadRequestError as exc:
                # Igual que en el motor de pruebas: hay modelos que solo
                # admiten tres tamaños, y lo dicen con un 400 antes de generar.
                if "size" not in str(exc).lower():
                    raise
                peticion["size"] = _tamano_de_catalogo(boceto.size)
                respuesta = _llamar(cliente, peticion)

        except openai.AuthenticationError as exc:
            raise ErrorDeMotor(
                "OpenAI ha rechazado la clave. Comprueba OPENAI_API_KEY en "
                "backend/.env, o crea otra en platform.openai.com/api-keys."
            ) from exc
        except openai.RateLimitError as exc:
            raise ErrorDeMotor(
                "OpenAI ha rechazado la petición por cuota: normalmente es que la "
                "cuenta no tiene saldo. Añade fondos en Settings → Billing."
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
            raise ErrorDeMotor(f"OpenAI ha rechazado la petición: {exc}") from exc
        except openai.APIConnectionError as exc:
            raise ErrorDeMotor(
                "No se ha podido conectar con OpenAI. Comprueba la conexión."
            ) from exc

        datos = respuesta.data[0] if respuesta.data else None
        if datos is None or not datos.b64_json:
            raise ErrorDeMotor("OpenAI ha respondido sin imagen.")

        imagen = Image.open(io.BytesIO(base64.b64decode(datos.b64_json))).convert("RGB")
        tokens = respuesta.usage.total_tokens if respuesta.usage else None
        return PrendaGenerada(imagen=imagen, proveedor=self.nombre, tokens=tokens)


def instruccion(con_color: bool) -> str:
    """El texto que se le da al modelo.

    En inglés, como las demás: lo sigue con más precisión. Y la mitad son
    prohibiciones porque el fallo conocido de este camino es que el modelo
    «mejora» el diseño: añade botones, cambia el escote, endereza el corte.
    """
    if con_color:
        color = (
            "COLOUR: the sketch is coloured. Use exactly the colours of the sketch, "
            "each on the same part of the garment. Do not invent a print or pattern "
            "that is not drawn."
        )
    else:
        color = (
            "COLOUR: the sketch is an uncoloured pencil drawing; its grey shading is "
            "only shading, not the colour of the garment. Make the whole garment in a "
            "plain, undyed, natural off-white fabric (ecru cotton-like, matte), with no "
            "print and no pattern."
        )

    return (
        "The image is a fashion designer's sketch. Produce a photorealistic studio "
        "product photograph of the SAME garment, as it would look once sewn. "
        "DESIGN: reproduce the drawn design faithfully. Keep the same silhouette, "
        "length, volume and proportions; the same neckline, shoulders, sleeves or "
        "straps; the same waist; and every seam, pleat, gather, drape, overlay, slit, "
        "train and closure, each in the same place as in the sketch. "
        "Do NOT add anything that is not drawn: no buttons, pockets, collars, belts, "
        "lace, embroidery, trims, logos or jewellery. Do NOT remove or simplify "
        "anything that is drawn. Do not restyle or modernise the design. "
        + color
        + " PRESENTATION: the garment alone, front view, the same view as the sketch, "
        "holding its three-dimensional shape as if worn by an invisible mannequin. "
        "No person, no face, no hair, no skin, no arms, no hands, no legs, no visible "
        "mannequin, no hanger. If the sketch shows a model, leave the model out and "
        "show what the garment looks like where the model covered it. "
        f"BACKGROUND: a plain, flat, uniform medium grey ({FONDO}) backdrop, with no "
        "gradient, no floor line, no props and no text. Soft even studio light and "
        "no cast shadow on the backdrop. The whole garment inside the frame, "
        "centred, with a clear margin all around."
    )


def tamano_de_salida(tamano: tuple[int, int]) -> tuple[int, int]:
    """El tamaño que se le pide: la proporción del boceto, a `LADO_MAYOR`.

    Múltiplo de 16 y entre 1:3 y 3:1, que es lo que admite la API.
    """
    ancho, alto = tamano
    proporcion = min(3.0, max(1 / 3, ancho / max(1, alto)))

    if proporcion >= 1.0:
        ancho, alto = LADO_MAYOR, LADO_MAYOR / proporcion
    else:
        ancho, alto = LADO_MAYOR * proporcion, LADO_MAYOR

    return (max(256, round(ancho / 16) * 16), max(256, round(alto / 16) * 16))


def boceto_a_color(boceto: Image.Image, mascara: Image.Image) -> bool:
    """¿La prenda del boceto está coloreada, o es solo lápiz?

    Decide lo que se le pide al modelo. Dejar que lo juzgue él es peor: el
    sombreado gris de un dibujo a lápiz lo toma por un vestido gris.

    Se mira dentro del recorte del boceto, que ya ha quitado a la figura: la
    piel y el pelo de un figurín tienen color aunque la prenda no lo tenga.
    """
    px = np.asarray(boceto.convert("RGB"), dtype=np.float32)
    gris = mascara.convert("L")
    if gris.size != boceto.size:
        gris = gris.resize(boceto.size, Image.Resampling.BILINEAR)
    dentro = np.asarray(gris) > 127
    if not dentro.any():
        return False

    croma = px.max(axis=2) - px.min(axis=2)
    return float((croma[dentro] > CROMA_DE_COLOR).mean()) >= MINIMO_COLOREADO


def parecido_de_silueta(del_boceto: Image.Image, de_la_prenda: Image.Image) -> float:
    """Cuánto coinciden las dos siluetas, de 0 a 1.

    El modelo no devuelve la prenda en el mismo sitio ni al mismo tamaño que el
    dibujo —le quita a la modelo y la centra—, así que no se pueden comparar
    píxel a píxel. Cada silueta se recorta a su caja y se lleva a un lienzo
    común conservando la proporción; lo que se mide es la intersección entre la
    unión.

    QUÉ MIDE Y QUÉ NO
    -----------------
    Mide el contorno: largo, vuelo, hombros, cola. NO ve nada de dentro —un
    escote distinto o unos botones de más no mueven el número—. Por eso
    acompaña a la comparación a ojo del usuario y no la sustituye.
    """
    a = _normalizada(del_boceto)
    b = _normalizada(de_la_prenda)
    if a is None or b is None:
        return 0.0

    union = float((a | b).sum())
    return float((a & b).sum()) / union if union else 0.0


def _normalizada(mascara: Image.Image) -> np.ndarray | None:
    """La silueta recortada a su caja y encajada, centrada, en un cuadrado."""
    binaria = mascara.convert("L").point(lambda v: 255 if v > 127 else 0)
    caja = binaria.getbbox()
    if caja is None:
        return None

    recorte = binaria.crop(caja)
    escala = LADO_DE_COMPARACION / max(recorte.size)
    tamano = (max(1, round(recorte.width * escala)), max(1, round(recorte.height * escala)))
    recorte = recorte.resize(tamano, Image.Resampling.BILINEAR)

    lienzo = Image.new("L", (LADO_DE_COMPARACION, LADO_DE_COMPARACION), 0)
    lienzo.paste(
        recorte,
        ((LADO_DE_COMPARACION - tamano[0]) // 2, (LADO_DE_COMPARACION - tamano[1]) // 2),
    )
    return np.asarray(lienzo) > 127
