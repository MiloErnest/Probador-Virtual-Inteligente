"""Contratos de entrada/salida de la autenticación.

DECISIÓN: el login recibe JSON, no un formulario OAuth2.

FastAPI ofrece `OAuth2PasswordRequestForm`, que regala el botón "Authorize"
de /docs, pero obliga a enviar `application/x-www-form-urlencoded` con un
campo llamado `username` que en realidad contiene un email. Eso ensucia el
contrato de la API y obliga al frontend —que ya envía JSON en todo lo demás—
a tratar el login como un caso especial.

Con `HTTPBearer` se conserva el botón Authorize en /docs (pegando el token en
lugar de escribir usuario y contraseña), que es un coste menor y solo afecta
a la exploración manual.
"""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    # Los mismos límites que en el registro: sin `max_length`, una cadena
    # enorme obligaría a bcrypt a trabajar de más en cada intento fallido.
    password: str = Field(min_length=1, max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    # Siempre "bearer". Se incluye porque es lo que espera cualquier cliente
    # que siga la convención de OAuth 2.0 al construir la cabecera.
    token_type: str = "bearer"
    # Segundos de validez. Evita que el cliente tenga que decodificar el
    # token para saber cuándo caduca.
    expires_in: int
