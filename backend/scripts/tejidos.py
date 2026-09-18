"""Genera mosaicos de tela de forma procedural.

PARA QUÉ
--------
El catálogo de ejemplo necesita telas, y una tela para este motor no es una
fotografía cualquiera: es un MOSAICO que se repite sin costura visible. Una
foto de catálogo normal trae el orillo, un doblez y a veces una mano, y al
repetirla sobre una camisa aparece la mano cuarenta veces.

Estas se dibujan con funciones periódicas, así que son seamless por
construcción: el borde derecho encaja con el izquierdo porque literalmente son
el mismo punto de la función.

NO SUSTITUYEN A LAS TELAS REALES
--------------------------------
Son telas creíbles, no telas reales. Para el producto de verdad, la tienda
textil aliada fotografía sus rollos y se recorta un cuadrado limpio de cada
uno: sale mejor y es gratis. Esto existe para que el catálogo funcione desde el
primer arranque sin depender de que alguien suba nada.

POR QUÉ SIMULAR EL HILO Y NO PONER UN COLOR PLANO
-------------------------------------------------
Porque el motor de retexturizado multiplica la tela por la luz de la prenda. Un
color plano multiplicado por una sombra da un color plano más oscuro: se ve
pintado. Con la trama del tejido, esa misma sombra cae sobre hilos con relieve
y el resultado se lee como tela.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

#: Lado del mosaico en píxeles. Múltiplo del paso del hilo para que la
#: repetición encaje exactamente.
LADO = 256

#: Píxeles por hilo. Con 8 la trama se aprecia al tamaño al que se ve una
#: prenda en pantalla; más fino se convierte en ruido gris.
PASO_HILO = 8


def _base(color: tuple[int, int, int]) -> np.ndarray:
    lienzo = np.zeros((LADO, LADO, 3), dtype=np.float32)
    lienzo[:] = np.array(color, dtype=np.float32) / 255.0
    return lienzo


def _malla() -> tuple[np.ndarray, np.ndarray]:
    ejes = np.arange(LADO, dtype=np.float32)
    return np.meshgrid(ejes, ejes)


def _relieve_del_hilo(posicion: np.ndarray) -> np.ndarray:
    """Perfil de un hilo: claro en el centro, oscuro en el canto.

    Es lo que hace que un tejido parezca tejido y no papel: cada hilo es un
    cilindro, y un cilindro iluminado brilla por el medio.
    """
    t = np.mod(posicion, PASO_HILO) / PASO_HILO
    return 0.86 + 0.28 * np.sin(np.pi * t)


def _ruido(semilla: int, fuerza: float) -> np.ndarray:
    """Irregularidad del hilo. Ninguna tela real es perfectamente uniforme."""
    generador = np.random.default_rng(semilla)
    return 1.0 + (generador.random((LADO, LADO), dtype=np.float32) - 0.5) * fuerza


def tafetan(color: tuple[int, int, int], semilla: int = 1) -> Image.Image:
    """Ligamento tafetán: un hilo por encima, uno por debajo.

    Es el tejido más común —el de una camisa de algodón— y el más sencillo:
    trama y urdimbre se alternan como un tablero de ajedrez.
    """
    x, y = _malla()
    celda_x = np.floor(x / PASO_HILO)
    celda_y = np.floor(y / PASO_HILO)
    trama_arriba = np.mod(celda_x + celda_y, 2) == 0

    relieve = np.where(trama_arriba, _relieve_del_hilo(y), _relieve_del_hilo(x))
    return _componer(_base(color), relieve * _ruido(semilla, 0.05))


def sarga(color: tuple[int, int, int], semilla: int = 2) -> Image.Image:
    """Ligamento sarga: el punto de cruce avanza y dibuja una diagonal.

    Es el tejido del vaquero y de la mayoría de las lanas de traje. La diagonal
    no es decorativa: sale de que cada pasada se desplaza un hilo.
    """
    x, y = _malla()
    celda_x = np.floor(x / PASO_HILO)
    celda_y = np.floor(y / PASO_HILO)
    trama_arriba = np.mod(celda_x + 2 * celda_y, 4) < 2

    relieve = np.where(trama_arriba, _relieve_del_hilo(y), _relieve_del_hilo(x))
    # La diagonal se refuerza con una onda suave en el sentido del cruce.
    relieve = relieve * (1.0 + 0.05 * np.sin(2 * np.pi * (x + y) / (PASO_HILO * 4)))
    return _componer(_base(color), relieve * _ruido(semilla, 0.05))


def lino(color: tuple[int, int, int], semilla: int = 3) -> Image.Image:
    """Lino: tafetán con hilo irregular.

    Lo que distingue al lino a simple vista son los engrosamientos del hilo.
    Se simulan modulando el grosor con una onda de periodo largo.
    """
    x, y = _malla()
    celda_x = np.floor(x / PASO_HILO)
    celda_y = np.floor(y / PASO_HILO)
    trama_arriba = np.mod(celda_x + celda_y, 2) == 0

    grosor = 1.0 + 0.1 * np.sin(2 * np.pi * x / 53) * np.sin(2 * np.pi * y / 61)
    relieve = np.where(trama_arriba, _relieve_del_hilo(y), _relieve_del_hilo(x)) * grosor
    return _componer(_base(color), relieve * _ruido(semilla, 0.11))


def rayas(
    color: tuple[int, int, int],
    segundo: tuple[int, int, int],
    ancho_raya: int = 32,
    semilla: int = 4,
) -> Image.Image:
    """Rayas verticales sobre tafetán.

    Verticales y no horizontales porque en confección la raya sigue el hilo de
    la urdimbre, que va a lo largo de la pieza.
    """
    x, y = _malla()
    lienzo = _base(color)
    en_la_raya = (np.mod(np.floor(x / ancho_raya), 2) == 1)[..., None]
    lienzo = np.where(en_la_raya, np.array(segundo, dtype=np.float32) / 255.0, lienzo)

    celda_x = np.floor(x / PASO_HILO)
    celda_y = np.floor(y / PASO_HILO)
    trama_arriba = np.mod(celda_x + celda_y, 2) == 0
    relieve = np.where(trama_arriba, _relieve_del_hilo(y), _relieve_del_hilo(x))
    return _componer(lienzo, relieve * _ruido(semilla, 0.05))


def cuadros(
    color: tuple[int, int, int],
    segundo: tuple[int, int, int],
    lado_cuadro: int = 42,
    semilla: int = 5,
) -> Image.Image:
    """Cuadro vichy: la misma raya en los dos sentidos.

    Donde se cruzan las dos bandas el color se acumula, igual que en la tela
    real, donde ahí coinciden hilo teñido de urdimbre y de trama.
    """
    x, y = _malla()
    banda_x = np.mod(np.floor(x / lado_cuadro), 2) == 1
    banda_y = np.mod(np.floor(y / lado_cuadro), 2) == 1

    claro = np.array(color, dtype=np.float32) / 255.0
    oscuro = np.array(segundo, dtype=np.float32) / 255.0
    medio = (claro + oscuro) / 2.0

    lienzo = np.zeros((LADO, LADO, 3), dtype=np.float32)
    lienzo[:] = claro
    lienzo = np.where((banda_x ^ banda_y)[..., None], medio, lienzo)
    lienzo = np.where((banda_x & banda_y)[..., None], oscuro, lienzo)

    celda_x = np.floor(x / PASO_HILO)
    celda_y = np.floor(y / PASO_HILO)
    trama_arriba = np.mod(celda_x + celda_y, 2) == 0
    relieve = np.where(trama_arriba, _relieve_del_hilo(y), _relieve_del_hilo(x))
    return _componer(lienzo, relieve * _ruido(semilla, 0.045))


def punto(color: tuple[int, int, int], semilla: int = 6) -> Image.Image:
    """Género de punto: mallas en forma de V, no hilos cruzados.

    Un jersey no está tejido, está hecho de bucles enlazados. Esa V es lo que
    se ve de cerca y lo que lo distingue de una camisa.
    """
    x, y = _malla()
    paso = PASO_HILO * 1.6
    columna = np.mod(x, paso) / paso
    fila = np.mod(y, paso) / paso

    # La V de cada malla: dos ramas que bajan desde los lados hacia el centro.
    v = np.abs(columna - 0.5) * 2.0
    relieve = 0.82 + 0.3 * np.sin(np.pi * np.clip(fila + v * 0.35, 0, 1))
    relieve = relieve * (0.95 + 0.1 * np.sin(np.pi * columna))
    return _componer(_base(color), relieve * _ruido(semilla, 0.07))


def _componer(lienzo: np.ndarray, relieve: np.ndarray) -> Image.Image:
    salida = np.clip(lienzo * relieve[..., None], 0.0, 1.0)
    return Image.fromarray((salida * 255.0).astype(np.uint8), mode="RGB")
