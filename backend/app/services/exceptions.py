"""Errores de dominio.

Los servicios lanzan estas excepciones; la capa de rutas las traduce a
códigos HTTP. Así el dominio no depende de FastAPI y puede reutilizarse desde
un script, un worker o un test sin arrastrar el framework.
"""


class DomainError(Exception):
    """Base de todos los errores de negocio."""


class NotFoundError(DomainError):
    """El recurso solicitado no existe."""


class ConflictError(DomainError):
    """La operación choca con el estado actual (p. ej. email duplicado)."""


class ValidationError(DomainError):
    """Los datos son sintácticamente válidos pero no aceptables."""


class AuthenticationError(DomainError):
    """No se ha podido identificar al usuario.

    Cubre a propósito tres casos distintos —el email no existe, la contraseña
    no coincide, la cuenta está desactivada— con un único error y un único
    mensaje. Distinguirlos en la respuesta permitiría averiguar qué correos
    están registrados probando el formulario de acceso.
    """
