"""Utilidades de seguridad: hasheo y verificación de contraseñas.

Decisión técnica: se usa la librería `bcrypt` directamente en lugar de
`passlib`. `passlib` 1.7.4 (la última publicada) falla al leer la versión de
`bcrypt` >= 4.1 y emite errores confusos; el proyecto lleva años sin
mantenimiento activo. La API de `bcrypt` es lo bastante simple como para no
necesitar una capa encima.

AVISO IMPORTANTE: bcrypt solo considera los primeros 72 bytes de la
contraseña y descarta el resto en silencio. Por eso los schemas de entrada
validan `max_length=72` (ver app/schemas/user.py). Sin esa validación, dos
contraseñas distintas que compartan los primeros 72 bytes serían
intercambiables.
"""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import settings

# Límite duro del algoritmo bcrypt.
MAX_PASSWORD_BYTES = 72

# Algoritmo de firma. Deliberadamente NO configurable por entorno: dejar que
# la configuración elija el algoritmo es un fallo clásico (basta con poner
# "none" para que cualquier token sin firma se acepte). HS256 es simétrico y
# suficiente mientras el mismo servicio emite y valida los tokens; si algún
# día los validara otro servicio, se pasaría a un algoritmo asimétrico.
JWT_ALGORITHM = "HS256"

# Distingue este token de cualquier otro que se emita en el futuro (por
# ejemplo, uno de recuperación de contraseña). Sin esta marca, un token
# emitido para otro fin serviría para iniciar sesión.
TOKEN_TYPE_ACCESS = "access"

# Hash señuelo con el que comparar cuando el email no existe. Verificar
# igualmente cuesta el mismo tiempo que una comprobación real, de modo que
# el tiempo de respuesta no revela qué correos están registrados.
# Corresponde a una contraseña aleatoria que nadie conoce.
DUMMY_PASSWORD_HASH = bcrypt.hashpw(
    bcrypt.gensalt(), bcrypt.gensalt()
).decode("utf-8")


class InvalidTokenError(Exception):
    """El token no es utilizable: mal firmado, caducado, o de otro tipo."""


def hash_password(password: str) -> str:
    """Devuelve el hash bcrypt de una contraseña en texto plano."""
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"La contraseña excede el límite de {MAX_PASSWORD_BYTES} bytes de bcrypt."
        )
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Comprueba una contraseña contra su hash. Nunca lanza excepción."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Hash con formato inválido o corrupto: se trata como fallo de login.
        return False


def create_access_token(
    user_id: int, *, expires_minutes: int | None = None
) -> tuple[str, int]:
    """Emite un token de acceso para un usuario.

    Devuelve `(token, segundos_de_validez)`. El segundo valor va en la
    respuesta del login para que el cliente sepa cuándo caduca sin tener que
    decodificar el token.

    `sub` se codifica como CADENA aunque el id sea un entero: el estándar JWT
    (RFC 7519) define `sub` como StringOrURI, y las librerías que validan
    estrictamente rechazan un `sub` numérico.
    """
    minutes = (
        settings.ACCESS_TOKEN_EXPIRE_MINUTES if expires_minutes is None else expires_minutes
    )
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=minutes)

    payload = {
        "sub": str(user_id),
        "type": TOKEN_TYPE_ACCESS,
        "iat": issued_at,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token, minutes * 60


def decode_access_token(token: str) -> int:
    """Valida un token de acceso y devuelve el id del usuario.

    Lanza `InvalidTokenError` ante cualquier problema —firma inválida, token
    caducado, tipo incorrecto, `sub` no numérico— y siempre con el mismo
    mensaje genérico: detallar por qué falló un token solo ayuda a quien está
    intentando forjar uno.

    `algorithms` se pasa como lista cerrada de un solo elemento. Es lo que
    impide el ataque de confusión de algoritmo, en el que un atacante cambia
    la cabecera del token para que se valide de otra forma.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Token inválido o caducado.") from exc

    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise InvalidTokenError("Token inválido o caducado.")

    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError("Token inválido o caducado.") from exc


# --- Verificación del correo (Ep5-Hu7) --------------------------------------

#: Un token de verificación NO sirve para entrar, y uno de acceso no sirve para
#: verificar: `decode_access_token` exige el tipo «access» y este exige el suyo.
TOKEN_TYPE_VERIFY_EMAIL = "verify_email"

#: Lo que dura el enlace del correo. Dos días dan margen a quien lo abre al día
#: siguiente; si caduca, se pide otro desde la aplicación.
VERIFY_EMAIL_EXPIRE_HOURS = 48


def create_email_verification_token(user_id: int, email: str) -> str:
    """Token del enlace de verificación. Lleva el correo que se verifica.

    Con el correo dentro, un enlace emitido para una dirección no verifica otra:
    si algún día se puede cambiar el correo, los enlaces viejos dejan de valer
    solos. Sin tabla: la firma ya dice que lo emitimos nosotros.
    """
    issued_at = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "email": email,
        "type": TOKEN_TYPE_VERIFY_EMAIL,
        "iat": issued_at,
        "exp": issued_at + timedelta(hours=VERIFY_EMAIL_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_email_verification_token(token: str) -> tuple[int, str]:
    """Devuelve `(id_de_usuario, correo)` de un enlace válido.

    Mismas garantías que el token de acceso: algoritmo cerrado, `exp`
    obligatorio, un único mensaje para cualquier fallo.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub", "email"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Enlace inválido o caducado.") from exc

    if payload.get("type") != TOKEN_TYPE_VERIFY_EMAIL:
        raise InvalidTokenError("Enlace inválido o caducado.")
    try:
        return int(payload["sub"]), str(payload["email"])
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError("Enlace inválido o caducado.") from exc
