"""Vestir a una persona con una prenda del taller.

EL CAMINO
---------
1. **Encontrar a la persona** en la foto con el analizador (`partes.py`) y
   encuadrarla. El modelo trabaja a 864 px de alto: si se le manda la foto
   entera de alguien que ocupa un tercio, la prenda sale con un tercio de esos
   píxeles. Encuadrada, la persona llena el cuadro.
2. **Vestirla** con el modelo configurado (`proveedor.py`).
3. **Conservar a la persona** (`componer`, con `conservar.py`): de la imagen
   generada solo entra la ropa que se prueba y la piel que esa ropa cambia.
   Lo demás son los píxeles originales, a la resolución original.

Si el modelo no está activado se sabe ANTES de analizar nada: ni se descarga
el analizador ni se gasta cuota para acabar diciendo que no hay modelo.

EL ENCUADRE DEPENDE DE LA PRENDA
--------------------------------
Para una prenda de arriba no hace falta mandar las piernas: se encuadra de la
cabeza a algo por debajo de la prenda que lleva puesta, y los 864 px del
modelo se gastan en el torso. Medido el 10/11/2026 en las dos fotos de
cuerpo entero que había: la persona pasa de 193 a 318 px de ancho en lo que
ve el modelo en una, y de 220 a 338 en la otra. En las dos, lo que genera el
modelo deja de ampliarse para volver a la foto. En una foto de medio cuerpo
el cuadro no cambia.

Lo que se arriesga es que la prenda nueva sea más larga que el cuadro —un
abrigo probado como «parte de arriba»— y quede cortada en recto. Se detecta
(la prenda llega al pie del cuadro, y el cuadro no es el final de la foto) y
se avisa de que se pruebe como vestido, que encuadra el cuerpo entero.

Solo la parte de arriba: en el taller no había ninguna prenda de abajo con
la que medir si el modelo trabaja bien sin ver la cabeza.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from PIL import Image

from app.models.try_on import GarmentCategory
from app.probador import partes as P
from app.probador.conservar import ROPA, Zona, paleta_de, zona_editable
from app.probador.proveedor import ModeloDePrueba, PeticionDePrueba, modelo_configurado
from app.textil.errores import ErrorDeMotor

#: Lado mayor al que se analizan las imágenes y se decide la zona. La zona se
#: difumina después, así que no necesita la resolución completa.
LADO_DE_ANALISIS = 1024

#: Proporción del cuadro que se le manda al modelo: la suya, 576 × 864.
PROPORCION = 2 / 3

#: Aire alrededor de la persona al encuadrarla, en fracción de su alto.
AIRE = 0.06

#: Para una prenda de arriba, cuánto de lo que hay entre el bajo de la prenda
#: que lleva puesta y los pies entra en el cuadro. Con 0,35 el corte cae a
#: medio muslo: caben las manos con los brazos caídos y una prenda nueva algo
#: más larga que la vieja.
BAJO_LA_PRENDA = 0.35

#: Una fila cuenta como «con prenda» si tiene al menos esta parte de la
#: anchura de la fila que más tiene: unas motas mal etiquetadas en los pies
#: no bajan el corte.
FILA_CON_PRENDA = 0.1

#: Menos que esto de persona en la foto, y no hay a quién vestir.
PERSONA_MINIMA = 0.02

#: Menos que esto de prenda nueva en la imagen generada, y el modelo no la ha
#: puesto: mejor decirlo que devolver la foto original como si fuera un
#: resultado.
PRENDA_MINIMA = 0.01

#: A partir de esta fracción de la foto cambiada fuera de la prenda, se avisa.
DESCARTE_A_AVISAR = 0.01

#: A partir de esta fracción del cuadro con ropa que no es de la prenda, se
#: avisa de que conviene pedir otra variante.
INVENTADO_A_AVISAR = 0.005

#: A partir de esta parte de la última fila del cuadro con prenda, la prenda
#: sigue por debajo de él.
PIE_A_AVISAR = 0.05


@dataclass(frozen=True)
class PersonaVestida:
    imagen: Image.Image
    proveedor: str
    #: Qué parte de la foto deja de ser la original. El resto es la foto.
    editado: float
    #: Qué parte de la foto había cambiado el modelo fuera de la prenda, y se
    #: ha deshecho.
    descartado: float
    aviso: str | None
    #: Lo que devolvió el modelo, sin componer, y la caja de la foto a la que
    #: corresponde. Se guarda para poder repetir la composición sin volver a
    #: gastar cuota.
    cruda: Image.Image | None = None
    caja: tuple[int, int, int, int] | None = None
    #: Con qué se llamó al modelo, si el modelo lo dice.
    parametros: str | None = None


@dataclass(frozen=True)
class Composicion:
    #: El cuadro de la persona, ya con la prenda.
    imagen: Image.Image
    #: De 0 a 1, al tamaño del cuadro: cuánto deja de ser la foto original.
    alfa: np.ndarray
    zona: Zona


def vestir_persona(
    persona: Image.Image,
    prenda: Image.Image,
    categoria: GarmentCategory,
    *,
    variante: int = 0,
    modelo: ModeloDePrueba | None = None,
    etiquetar: Callable[[Image.Image, tuple[int, int]], np.ndarray] | None = None,
) -> PersonaVestida:
    """Devuelve la foto de `persona` con `prenda` puesta.

    `modelo` y `etiquetar` se inyectan en las pruebas automáticas, que no
    pueden llamar a Hugging Face ni descargar el analizador.
    """
    modelo = modelo or modelo_configurado()
    etiquetar = etiquetar or P.etiquetar
    persona = persona.convert("RGB")

    # 1. Encontrar a la persona y encuadrarla.
    tamano = _reducido(persona.size, LADO_DE_ANALISIS)
    etiquetas = etiquetar(persona, tamano)
    if (etiquetas != P.FONDO).mean() < PERSONA_MINIMA:
        raise ErrorDeMotor(
            "No se ve a ninguna persona en la foto. Hace falta una foto de cuerpo "
            "entero o de medio cuerpo, con la persona bien visible."
        )
    escala = persona.width / tamano[0]
    caja = _encuadre_por_categoria(etiquetas, escala, persona.size, categoria)
    recorte = persona.crop(caja)

    # 2. Vestirla.
    peticion = PeticionDePrueba(
        persona=recorte, prenda=prenda, categoria=categoria, variante=variante
    )
    generada = modelo.vestir(peticion)
    if abs(generada.width / generada.height - recorte.width / recorte.height) > 0.03:
        raise ErrorDeMotor(
            "El modelo ha devuelto una imagen con otro encuadre, y no se puede "
            "superponer a tu foto sin deformarla."
        )

    # 3. Conservar a la persona.
    return recomponer(
        persona,
        caja,
        generada,
        prenda,
        categoria,
        proveedor=modelo.nombre,
        parametros=modelo.parametros(peticion) if hasattr(modelo, "parametros") else None,
        etiquetar=etiquetar,
    )


def recomponer(
    persona: Image.Image,
    caja: tuple[int, int, int, int],
    generada: Image.Image,
    prenda: Image.Image,
    categoria: GarmentCategory,
    *,
    proveedor: str,
    parametros: str | None = None,
    etiquetar: Callable[[Image.Image, tuple[int, int]], np.ndarray] | None = None,
) -> PersonaVestida:
    """La foto con la prenda, a partir de lo que el modelo YA devolvió.

    Es el paso 3 solo. No llama al modelo ni gasta cuota: con la foto, la
    caja, la salida cruda y la prenda —que se guardan con cada prueba— se
    puede repetir cuando `conservar.py` mejora (`scripts/recomponer.py`).
    """
    persona = persona.convert("RGB")
    recorte = persona.crop(caja)
    compuesta = componer(recorte, generada, prenda, categoria, etiquetar)
    zona = compuesta.zona
    if zona.prenda_nueva < PRENDA_MINIMA:
        raise ErrorDeMotor(
            "El modelo no ha llegado a colocar la prenda. Suele pasar con posturas muy "
            "cerradas o con la prenda muy tapada; prueba con otra foto."
        )

    salida = persona.copy()
    salida.paste(compuesta.imagen, caja[:2])

    total = persona.width * persona.height
    parte = (recorte.width * recorte.height) / total
    descartado = zona.descartado * parte
    # La prenda llega al pie del cuadro y la foto sigue por debajo: está cortada.
    cortada = caja[3] < persona.height - 2 and zona.prenda_al_pie > PIE_A_AVISAR
    return PersonaVestida(
        imagen=salida,
        proveedor=proveedor,
        editado=float(compuesta.alfa.sum()) / total,
        descartado=descartado,
        aviso=_aviso(descartado, zona.inventado, cortada),
        cruda=generada,
        caja=caja,
        parametros=parametros,
    )


def componer(
    recorte: Image.Image,
    generada: Image.Image,
    prenda: Image.Image,
    categoria: GarmentCategory,
    etiquetar: Callable[[Image.Image, tuple[int, int]], np.ndarray] | None = None,
) -> Composicion:
    """El cuadro de la persona con la prenda: la foto, salvo donde manda el modelo.

    No llama a ningún modelo de imagen: con el cuadro, la salida cruda y la
    prenda guardados, se puede repetir tantas veces como haga falta.
    """
    import cv2

    etiquetar = etiquetar or P.etiquetar
    recorte = recorte.convert("RGB")
    generada = generada.convert("RGB")

    trabajo = _reducido(recorte.size, LADO_DE_ANALISIS)
    persona_px = np.asarray(recorte.resize(trabajo, Image.Resampling.LANCZOS), dtype=np.float32)
    generada_px = np.asarray(generada.resize(trabajo, Image.Resampling.LANCZOS), dtype=np.float32)
    zona = zona_editable(
        persona_px,
        generada_px,
        etiquetar(recorte, trabajo),
        etiquetar(generada, trabajo),
        categoria,
        paleta=paleta_de(prenda),
    )

    alfa = cv2.resize(zona.alfa, recorte.size, interpolation=cv2.INTER_LINEAR)
    original = np.asarray(recorte, dtype=np.float32)
    fuente = np.asarray(generada.resize(recorte.size, Image.Resampling.LANCZOS), dtype=np.float32)
    if zona.fondo is not None:
        # Donde la imagen generada enseña fondo, el de la foto. Es un campo
        # suave: ampliarlo no le quita nada.
        relleno = cv2.resize(zona.relleno, recorte.size, interpolation=cv2.INTER_LINEAR)[..., None]
        fondo = cv2.resize(zona.fondo, recorte.size, interpolation=cv2.INTER_LINEAR)
        fuente = fuente * (1.0 - relleno) + fondo * relleno

    mezcla = original * (1.0 - alfa[..., None]) + fuente * alfa[..., None]
    imagen = Image.fromarray(np.clip(mezcla + 0.5, 0, 255).astype(np.uint8))
    return Composicion(imagen=imagen, alfa=alfa, zona=zona)


def _aviso(descartado: float, inventado: float = 0.0, cortada: bool = False) -> str | None:
    avisos = []
    if inventado >= INVENTADO_A_AVISAR:
        avisos.append(
            "El modelo le ha añadido a la prenda partes que no son suyas (otra capa, "
            "otras mangas). Donde tapaban tu piel se han quitado; si aún se nota, "
            "pide otra variante."
        )
    if cortada:
        avisos.append(
            "La prenda llega hasta el borde de lo que se le enseñó al modelo, así que "
            "puede ser más larga de lo que se ve. Pruébala como «Vestido o mono», que "
            "encuadra el cuerpo entero."
        )
    if descartado >= DESCARTE_A_AVISAR:
        avisos.append(
            f"El modelo también había cambiado un {descartado:.0%} de tu foto fuera de "
            "la prenda (fondo, cara, manos u otra ropa). Se ha deshecho: ahí ves tu foto "
            "original."
        )
    return " ".join(avisos) or None


def _reducido(tamano: tuple[int, int], lado: int) -> tuple[int, int]:
    ancho, alto = tamano
    escala = min(1.0, lado / max(ancho, alto))
    return max(8, round(ancho * escala)), max(8, round(alto * escala))


def _encuadre_por_categoria(
    etiquetas: np.ndarray, escala: float, tamano: tuple[int, int], categoria: GarmentCategory
) -> tuple[int, int, int, int]:
    """La caja que se le manda al modelo: la persona, o la parte que la prenda viste.

    Ver la cabecera. Si la persona no lleva nada que el analizador reconozca
    como prenda de arriba, no hay referencia para cortar y va el cuerpo entero.
    """
    figura = etiquetas != P.FONDO
    if categoria is GarmentCategory.TOP:
        por_fila = np.isin(etiquetas, list(ROPA[GarmentCategory.TOP])).sum(axis=1)
        con_prenda = np.nonzero(por_fila >= max(1.0, FILA_CON_PRENDA * por_fila.max()))[0]
        con_figura = np.nonzero(figura.any(axis=1))[0]
        if len(con_prenda) and len(con_figura):
            bajo, pies = int(con_prenda[-1]), int(con_figura[-1])
            corte = bajo + round(BAJO_LA_PRENDA * max(0, pies - bajo))
            figura = figura.copy()
            figura[corte + 1 :] = False
    return _encuadre(figura, escala, tamano)


def _encuadre(
    figura: np.ndarray, escala: float, tamano: tuple[int, int]
) -> tuple[int, int, int, int]:
    """Caja de la figura en la foto original, con aire y en la proporción del modelo."""
    filas = np.nonzero(figura.any(axis=1))[0]
    columnas = np.nonzero(figura.any(axis=0))[0]
    x0, x1 = columnas[0] * escala, (columnas[-1] + 1) * escala
    y0, y1 = filas[0] * escala, (filas[-1] + 1) * escala

    aire = AIRE * (y1 - y0)
    x0, x1, y0, y1 = x0 - aire, x1 + aire, y0 - aire, y1 + aire
    ancho, alto = x1 - x0, y1 - y0
    if ancho / alto < PROPORCION:
        ancho = alto * PROPORCION
    else:
        alto = ancho / PROPORCION
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

    limite_x, limite_y = tamano
    ancho, alto = min(ancho, limite_x), min(alto, limite_y)
    x0 = min(max(0.0, cx - ancho / 2), limite_x - ancho)
    y0 = min(max(0.0, cy - alto / 2), limite_y - alto)
    return round(x0), round(y0), round(x0 + ancho), round(y0 + alto)
