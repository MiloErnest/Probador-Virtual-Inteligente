"""Errores del motor textil.

POR QUÉ EL MOTOR TIENE SU PROPIO ERROR
--------------------------------------
Al principio lanzaba `ValidationError`, que vive en `app/services/`. Parecía
inocente y creaba un ciclo de importación: el motor importaba la capa de
servicios, y la capa de servicios importa el motor. Python lo dejaba pasar
mientras `app.main` fuera lo primero en cargarse —que es lo que ocurre al
arrancar y en los tests— y reventaba en cuanto un script importaba el motor
directamente.

Pero el ciclo era el síntoma. El problema de fondo es de capas: el motor está
POR DEBAJO de los servicios y no debe saber que existen. Recibe imágenes y
devuelve imágenes; que eso acabe siendo un 422 en una respuesta HTTP es asunto
de otra capa.

Así que el motor lanza lo suyo, y `FabricTrialService` lo traduce. Es una línea
de traducción a cambio de que cada capa pueda existir sin la de encima.
"""


class ErrorDeMotor(Exception):
    """Algo ha impedido vestir la prenda, y el usuario puede arreglarlo.

    Falta el mosaico de la tela, el motor de IA no está configurado, la clave
    no vale, no hay saldo. Son cosas con solución, y el mensaje la dice.

    Lo que NO es: un fallo del código. Eso sube sin envolver y se registra como
    lo que es.
    """
