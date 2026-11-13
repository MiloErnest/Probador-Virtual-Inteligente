"""Contratos de entrada/salida de la API para usuarios.

Regla: `password_hash` NUNCA aparece en un schema de salida.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    # max_length=72: bcrypt ignora en silencio todo lo que exceda 72 bytes.
    # Ver app/core/security.py.
    password: str = Field(min_length=8, max_length=72)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    is_active: bool
    #: Si confirmó su correo (Ep5-Hu7). Sin él no puede generar prendas con IA.
    email_verified: bool = False
    created_at: datetime
    updated_at: datetime


class VerifyEmailRequest(BaseModel):
    """El token del enlace que llegó por correo."""

    token: str = Field(min_length=10, max_length=2048)
