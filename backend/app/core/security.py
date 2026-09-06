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

import bcrypt

# Límite duro del algoritmo bcrypt.
MAX_PASSWORD_BYTES = 72


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
