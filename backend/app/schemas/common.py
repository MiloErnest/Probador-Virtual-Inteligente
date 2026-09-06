"""Schemas compartidos entre módulos."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    environment: str
    database: Literal["up", "down"]


class MessageResponse(BaseModel):
    message: str
