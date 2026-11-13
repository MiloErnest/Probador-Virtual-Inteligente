"""Enviar correos: por ahora, solo el enlace para verificar el buzón (Ep5-Hu7).

DOS CAMINOS
-----------
- **SMTP** (`SMTP_HOST` puesto): `smtplib` de la biblioteca estándar, con
  STARTTLS. Sin dependencias nuevas: un servicio de correo transaccional con su
  propio SDK sería infraestructura «por si acaso» (regla 11) para un correo por
  registro.
- **Registro del servidor** (sin `SMTP_HOST`): el correo NO sale; se escribe en
  el log con el enlace, para poder verificar una cuenta en local. Se dice tal
  cual en el log, para que nadie crea que se envió.

El envío corre en segundo plano (`BackgroundTasks`): un servidor SMTP lento no
debe retrasar el registro. Si falla, se registra y la cuenta sigue sin
verificar; desde la aplicación se puede pedir otro enlace.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol

from app.core.config import settings

registro = logging.getLogger("app.correo")


class Correo(Protocol):
    def enviar(self, destino: str, asunto: str, texto: str) -> None: ...


class CorreoSMTP:
    def __init__(self, host: str, puerto: int, usuario: str, clave: str, remitente: str) -> None:
        self.host, self.puerto = host, puerto
        self.usuario, self.clave, self.remitente = usuario, clave, remitente

    def enviar(self, destino: str, asunto: str, texto: str) -> None:
        mensaje = EmailMessage()
        mensaje["From"] = self.remitente
        mensaje["To"] = destino
        mensaje["Subject"] = asunto
        mensaje.set_content(texto)
        with smtplib.SMTP(self.host, self.puerto, timeout=20) as servidor:
            servidor.starttls()
            if self.usuario:
                servidor.login(self.usuario, self.clave)
            servidor.send_message(mensaje)


class CorreoEnElRegistro:
    """No envía: deja el correo en el log del servidor. Para desarrollo."""

    def enviar(self, destino: str, asunto: str, texto: str) -> None:
        registro.warning(
            "CORREO NO ENVIADO (falta SMTP_HOST en backend/.env). Para %s — %s\n%s",
            destino,
            asunto,
            texto,
        )


def correo_configurado() -> Correo:
    """El único punto que decide cómo sale un correo."""
    if settings.SMTP_HOST:
        return CorreoSMTP(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            settings.SMTP_USER,
            settings.SMTP_PASSWORD,
            settings.MAIL_FROM or settings.SMTP_USER,
        )
    return CorreoEnElRegistro()


def texto_de_verificacion(nombre: str, enlace: str, horas: int) -> tuple[str, str]:
    asunto = "Confirma tu correo — Probador Virtual de Telas"
    texto = (
        f"Hola, {nombre}:\n\n"
        "Para terminar de crear tu cuenta, confirma que este correo es tuyo abriendo "
        f"este enlace:\n\n{enlace}\n\n"
        f"El enlace vale {horas} horas. Hasta confirmarlo puedes probar telas, pero no "
        "generar prendas con IA a partir de tus bocetos.\n\n"
        "Si no creaste esta cuenta, ignora este correo.\n"
    )
    return asunto, texto


def enviar_verificacion(correo: Correo, destino: str, nombre: str, enlace: str, horas: int) -> None:
    """Para `BackgroundTasks`: un fallo se registra, no rompe nada."""
    asunto, texto = texto_de_verificacion(nombre, enlace, horas)
    try:
        correo.enviar(destino, asunto, texto)
    except (OSError, smtplib.SMTPException) as exc:
        # Sin la dirección completa en el log: basta el dominio para buscar.
        registro.error(
            "No se pudo enviar el correo de verificación a *@%s: %s",
            destino.rsplit("@", 1)[-1],
            type(exc).__name__,
        )
