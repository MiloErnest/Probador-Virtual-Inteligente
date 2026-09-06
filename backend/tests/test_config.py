"""Pruebas de la carga de configuración.

Existen por un fallo real: `CORS_ORIGINS` está tipado como `list[str]`, y
pydantic-settings intenta decodificar como JSON los campos de tipo complejo
ANTES de ejecutar los validadores. Una lista separada por comas hacía fallar
el arranque completo de la aplicación con `SettingsError`.

`_env_file=None` evita que estas pruebas lean el `.env` del desarrollador:
así el resultado no depende de cómo tenga configurada su máquina.
"""

import pytest

from app.core.config import Settings


def test_cors_origins_accepts_a_comma_separated_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")

    settings = Settings(_env_file=None)

    assert settings.CORS_ORIGINS == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_cors_origins_tolerates_spaces_and_trailing_commas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", " http://a.test , http://b.test ,")

    settings = Settings(_env_file=None)

    assert settings.CORS_ORIGINS == ["http://a.test", "http://b.test"]


def test_cors_origins_accepts_a_single_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")

    settings = Settings(_env_file=None)

    assert settings.CORS_ORIGINS == ["http://localhost:5173"]


def test_cors_origins_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    settings = Settings(_env_file=None)

    assert settings.CORS_ORIGINS == ["http://localhost:5173"]


def test_max_upload_bytes_derives_from_megabytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_UPLOAD_MB", "8")

    settings = Settings(_env_file=None)

    assert settings.max_upload_bytes == 8 * 1024 * 1024
