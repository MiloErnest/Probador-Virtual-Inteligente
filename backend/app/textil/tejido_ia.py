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
from app.textil.filtros import desenfocar

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


def reconstruir_estampado(
    franja: Image.Image, descripcion: str, *, repetible: bool = True
) -> tuple[Image.Image, int | None]:
    """Completa un estampado del que solo se ve una franja en la foto del rollo.

    PARA QUÉ, Y CON QUÉ HONESTIDAD
    ------------------------------
    En una estantería, de cada rollo se ve el lomo: una franja de dos dedos de
    un dibujo que mide un palmo. Con eso no hay forma determinista de
    reconstruir el motivo entero — falta la información. Un modelo generativo sí
    puede completarlo coherentemente con lo que se ve: mismos colores, mismo
    estilo, misma escala.

    Pero es una RECONSTRUCCIÓN, no la tela exacta, y la ficha lo tiene que
    decir. Es el uso correcto de la IA en este proyecto: no hay ninguna prenda
    que conservar, solo un trozo de tela plano que completar.
    """
    if not settings.OPENAI_API_KEY:
        raise ErrorDeMotor("Falta OPENAI_API_KEY en backend/.env.")

    import openai
    from openai import OpenAI

    cliente = OpenAI(
        api_key=settings.OPENAI_API_KEY, timeout=settings.OPENAI_TIMEOUT_SECONDS, max_retries=0
    )
    peticion = {
        "model": settings.OPENAI_TEXTURE_MODEL,
        "image": ("franja.png", _a_png(franja.convert("RGB")), "image/png"),
        "prompt": (
            f"The input is a narrow photo strip of a rolled bolt of {descripcion}, seen "
            "on a shop shelf: only a thin band of the printed pattern is visible, and it "
            "is curved and unevenly lit. Reconstruct the COMPLETE printed pattern as a "
            "flat, top-down, evenly lit square fabric swatch. Keep exactly the same "
            "motifs, the same colours and the same print style and scale as the strip. "
            "The print must fill the whole frame edge to edge. No roll, no shelf, no "
            "folds, no shadows, no background, no text."
        ),
        "size": f"{LADO}x{LADO}",
        "quality": settings.OPENAI_TEXTURE_QUALITY,
        "n": 1,
    }
    try:
        respuesta = _editar(cliente, peticion)
    except openai.RateLimitError as exc:
        raise ErrorDeMotor("OpenAI ha rechazado la petición por cuota.") from exc
    except openai.BadRequestError as exc:
        raise ErrorDeMotor(f"OpenAI ha rechazado la petición: {exc}") from exc
    except openai.APIConnectionError as exc:
        raise ErrorDeMotor("No se ha podido conectar con OpenAI.") from exc

    datos = respuesta.data[0] if respuesta.data else None
    if datos is None or not datos.b64_json:
        raise ErrorDeMotor("OpenAI ha respondido sin imagen.")
    imagen = Image.open(io.BytesIO(base64.b64decode(datos.b64_json))).convert("RGB")
    tokens = respuesta.usage.total_tokens if respuesta.usage else None
    # `repetible=False` devuelve la salida cruda del modelo, para guardarla: así
    # una mejora del cierre de juntas se aplica después sin volver a pagar.
    return (hacer_repetible(imagen) if repetible else imagen), tokens


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


#: Anchura del suavizado a lo largo del corte, en píxeles. Lo justo para quitar
#: el escalón de un píxel sin volver a superponer las dos imágenes.
SUAVIZADO_DEL_CORTE = 3.0

#: Por encima de esta correlación, un eje se considera PERIÓDICO: el dibujo se
#: repite con un paso fijo (un cuadro, una raya). Por debajo es una trama
#: estadística (un tafetán liso, un punto) y se puede fundir sin riesgo.
PERIODICIDAD_MINIMA = 0.35

#: Mínimo de repeticiones que tiene que caber en el mosaico para fiarse de un
#: período medido. Con 3 no se detectaba el cuadro de un vichy generado, que
#: cabe dos veces y media en su propio mosaico; con menos de 2, un pico de la
#: autocorrelación puede ser casual.
REPETICIONES_MINIMAS = 2


def hacer_repetible(imagen: Image.Image) -> Image.Image:
    """Convierte cualquier imagen en un mosaico que se repite sin junta.

    DOS CAMINOS, Y ELEGIR MAL EL PRIMERO ROMPIÓ LOS CUADROS
    -------------------------------------------------------
    La primera versión fundía la imagen consigo misma desplazada media anchura.
    Con una trama aleatoria —un tafetán, un punto— funciona perfecto. Con un
    **patrón periódico** es un desastre salvo que el desplazamiento sea múltiplo
    exacto del período: si no, superpone dos cuadros desalineados. Los dos vichy
    del catálogo salieron así, con los cuadros fantasmales. Y la métrica de
    junta decía que estaban bien, porque medía la costura y no el dibujo.

    LA SOLUCIÓN: FUNDIR DESPLAZANDO UN MÚLTIPLO DEL PERÍODO
    ------------------------------------------------------
    Si el dibujo se repite cada *p* píxeles, la imagen desplazada *k·p* es
    idéntica a sí misma, así que fundirla con ella no desalinea nada. Y la
    continuidad en el borde se cumple con CUALQUIER desplazamiento, no solo con
    media anchura. Así que se mide el período con la autocorrelación y se funde
    desplazando el múltiplo del período más cercano a media anchura.

    Un solo algoritmo sirve para todo: un cuadro, una raya (periódica en un eje
    y estadística en el otro), la trama fina de un tafetán, o una tela sin
    período ninguno, donde se funde a media anchura como siempre.

    Lo que NO se hace, y se probó: recortar un número entero de períodos. Con el
    período redondeado a píxeles enteros, el vichy procedural —tres cuadros de
    85,33 px, perfecto de origen— se recortaba a 3 × 84 y salía con junta.
    """
    px = np.asarray(imagen.convert("RGB"), dtype=np.float32) / 255.0
    alto, ancho = px.shape[:2]
    lado = min(alto, ancho)
    px = px[(alto - lado) // 2 : (alto - lado) // 2 + lado, (ancho - lado) // 2 : (ancho - lado) // 2 + lado]

    # Se reescala ANTES de fundir: después, el reescalado trataría el borde como
    # borde y no como la continuación del lado opuesto, y rompería la junta.
    recorte = Image.fromarray(np.clip(px * 255.0, 0, 255).astype(np.uint8), mode="RGB")
    px = np.asarray(recorte.resize((LADO, LADO), Image.Resampling.LANCZOS), dtype=np.float32) / 255.0

    for eje in (1, 0):
        px = _fundir(px, eje, _desplazamiento(px, eje))

    return Image.fromarray(np.clip(px * 255.0, 0, 255).astype(np.uint8), mode="RGB")


def _desplazamiento(px: np.ndarray, eje: int) -> int:
    """El múltiplo del período más cercano a media anchura; o media anchura."""
    n = px.shape[eje]
    periodo = medir_periodo(px, eje)
    if periodo is None:
        return n // 2
    veces = max(1, round((n / 2) / periodo))
    desplazamiento = round(veces * periodo)
    return desplazamiento if 0 < desplazamiento < n else n // 2


def medir_periodo(px: np.ndarray, eje: int) -> float | None:
    """El paso con el que se repite el dibujo en un eje, o None si no se repite.

    Por autocorrelación: se promedia la imagen a lo largo del OTRO eje —un
    cuadro vichy visto de lado es una onda cuadrada— y se busca el primer pico
    fuerte después del cero. Con la transformada de Fourier cuesta lo mismo
    para cualquier tamaño.

    EN FRACCIONES DE PÍXEL. Un vichy de tres cuadros en 256 px tiene período
    85,33, y redondearlo a 84 dejaba 4 px de error acumulado en el borde. Se
    ajusta una parábola a los tres valores alrededor del pico, que es la forma
    estándar de afinar un máximo muestreado.
    """
    brillo = px.mean(axis=2)
    perfil = brillo.mean(axis=1 - eje)
    perfil = perfil - perfil.mean()
    n = perfil.size
    if n < 16 or float(perfil.std()) < 1e-3:
        return None

    espectro = np.fft.rfft(perfil, n=2 * n)
    auto = np.fft.irfft(espectro * np.conj(espectro))[:n]
    auto = auto / (auto[0] or 1.0)

    # El primer pico tras el cero, sin dejarse engañar por el rizado fino del
    # hilo: se exige que el valor haya bajado de verdad antes de volver a subir.
    maximo = n // REPETICIONES_MINIMAS
    bajado = False
    for desfase in range(2, maximo):
        if auto[desfase] < 0.0:
            bajado = True
        if (
            bajado
            and auto[desfase] >= PERIODICIDAD_MINIMA
            and auto[desfase] >= auto[desfase - 1]
            and auto[desfase] >= auto[desfase + 1]
        ):
            antes, pico, despues = auto[desfase - 1], auto[desfase], auto[desfase + 1]
            curvatura = antes - 2.0 * pico + despues
            ajuste = 0.5 * (antes - despues) / curvatura if curvatura < 0 else 0.0
            return float(desfase + np.clip(ajuste, -0.5, 0.5))
    return None


def _fundir(px: np.ndarray, eje: int, desplazamiento: int) -> np.ndarray:
    """Cierra la junta en un eje, cortando por donde menos se note.

    En los bordes manda la imagen desplazada, cuyas columnas extremas eran
    VECINAS en el original: por eso encajan al repetir, sea cual sea el
    desplazamiento. En el centro manda el original. Queda decidir cómo se pasa
    de una a otra, y ahí está todo.

    NO SE MEZCLA: SE CORTA
    ----------------------
    Mezclando con una rampa, un tafetán o un punto quedan perfectos — son
    tramas finas y la mezcla no se ve. Con un motivo grande, las hojas de una
    palmera salían dobles y medio transparentes en toda la franja de mezcla.

    Es el problema que resuelve el *image quilting* (Efros y Freeman, SIGGRAPH
    2001): en la zona donde se solapan las dos imágenes se busca el camino por
    donde MENOS se diferencian, y se corta por ahí. El paso de una a otra sigue
    el contorno de las hojas en vez de superponerlas. Tres píxeles de suavizado
    a lo largo del corte quitan el escalón sin volver a crear fantasmas.

    Y si el desplazamiento es múltiplo del período, las dos imágenes son la
    misma en todo el solape, el coste es cero en todas partes y el corte da
    igual: sirve tal cual para cuadros y rayas.
    """
    if eje == 0:
        return np.swapaxes(_fundir(np.swapaxes(px, 0, 1), 1, desplazamiento), 0, 1)

    n = px.shape[1]
    desplazada = np.roll(px, desplazamiento, axis=1)
    banda = max(4, round(n * FUNDIDO))

    # Máscara de 1 = original, 0 = desplazada. Centro: original. Bordes:
    # desplazada. En cada banda, la frontera la pone el corte de mínimo error.
    usar_original = np.ones(px.shape[:2], dtype=np.float32)
    diferencia = ((px - desplazada) ** 2).sum(axis=2)

    # El corte no puede tocar el borde exterior de la banda: ahí tiene que
    # mandar la desplazada, o la junta deja de encajar. Ni el interior, o no
    # queda sitio para suavizarlo.
    margen = max(2, round(SUAVIZADO_DEL_CORTE * 3))
    prohibido = float(diferencia.max()) * banda * 4 + 1.0
    coste_izquierda = diferencia[:, :banda].copy()
    coste_izquierda[:, :margen] = prohibido
    coste_izquierda[:, -margen:] = prohibido
    coste_derecha = diferencia[:, n - banda:].copy()
    coste_derecha[:, :margen] = prohibido
    coste_derecha[:, -margen:] = prohibido

    izquierda = _corte_minimo(coste_izquierda)
    derecha = _corte_minimo(coste_derecha)
    columnas = np.arange(n)[None, :]
    usar_original[columnas < izquierda[:, None]] = 0.0
    usar_original[columnas > (n - banda + derecha)[:, None]] = 0.0

    suave = desenfocar(usar_original, SUAVIZADO_DEL_CORTE)
    return px * suave[..., None] + desplazada * (1.0 - suave[..., None])


def _corte_minimo(coste: np.ndarray) -> np.ndarray:
    """Camino de arriba abajo de coste mínimo, moviéndose a lo sumo un píxel por fila.

    Programación dinámica, la misma del *seam carving*: se acumula el coste
    fila a fila quedándose con el mejor de los tres vecinos de encima, y se
    reconstruye el camino desde abajo. Devuelve, para cada fila, la columna del
    corte.
    """
    alto, ancho = coste.shape
    acumulado = coste.astype(np.float64).copy()
    for y in range(1, alto):
        arriba = acumulado[y - 1]
        izquierda = np.concatenate([[np.inf], arriba[:-1]])
        derecha = np.concatenate([arriba[1:], [np.inf]])
        acumulado[y] += np.minimum(np.minimum(izquierda, arriba), derecha)

    camino = np.empty(alto, dtype=np.int64)
    camino[-1] = int(np.argmin(acumulado[-1]))
    for y in range(alto - 2, -1, -1):
        x = camino[y + 1]
        desde, hasta = max(0, x - 1), min(ancho, x + 2)
        camino[y] = desde + int(np.argmin(acumulado[y, desde:hasta]))
    return camino


def medir_junta(mosaico: Image.Image) -> float:
    """Cuánto se nota la unión al repetir. 0 es invisible; por encima de 1, se ve.

    SE COMPARA CON LO QUE DEBERÍA HABER, NO CON UN PROMEDIO
    ------------------------------------------------------
    La versión anterior comparaba el salto del borde con el salto medio entre
    vecinas. En una raya casi todas las vecinas son iguales, así que cualquier
    borde que cayera en un cambio de color —aunque fuera perfecto— daba un
    número enorme: 14,5 las rayas marineras, siendo impecables. Y al revés: dio
    por buenos los vichy fantasmales, porque medía la costura y no el dibujo.

    Ahora, si el eje es periódico, el paso del último píxel al primero se
    compara con el paso equivalente UN PERÍODO ANTES, que es lo que el dibujo
    dice que tiene que haber ahí. Si no lo es, con el salto típico de dentro.
    """
    px = np.asarray(mosaico.convert("RGB"), dtype=np.float32) / 255.0
    peor = 0.0
    for eje in (0, 1):
        n = px.shape[eje]
        vecinas = np.abs(np.diff(px, axis=eje)).mean(axis=(2, 1 - eje))
        tipico = float(np.percentile(vecinas, 95)) or 1e-6

        salto = np.take(px, 0, axis=eje) - np.take(px, n - 1, axis=eje)
        periodo = medir_periodo(px, eje)
        if periodo is not None:
            k = round(periodo)
            esperado = np.take(px, n - k, axis=eje) - np.take(px, n - k - 1, axis=eje)
            desvio = float(np.abs(salto - esperado).mean())
        else:
            desvio = float(np.abs(salto).mean())
        peor = max(peor, desvio / tipico)
    return peor


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
