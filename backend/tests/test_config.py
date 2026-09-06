"""Pruebas de la carga de configuración.

Existen por un fallo real: `CORS_ORIGINS` está tipado como `list[str]`, y
pydantic-settings intenta decodificar como JSON los campos de tipo complejo
ANTES de ejecutar los validadores. Una lista separada por comas hacía fallar
el arranque completo de la aplicación con `SettingsError`.

`_env_file=None` evita que estas pruebas lean el `.env` del desarrollador:
así el resultado no depende de cómo tenga configurada su máquina.
"""

import secrets

import pytest
from pydantic import ValidationError

from app.core.config import DEFAULT_INSECURE_SECRET, Settings


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


# --- SECRET_KEY (Etapa 2) ----------------------------------------------------
#
# Firmar tokens con la clave de ejemplo, que está escrita en el repositorio,
# equivale a no tener autenticación: cualquiera puede emitir un token válido
# para cualquier usuario. En producción eso debe impedir el arranque.


def test_production_refuses_to_start_with_the_example_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", DEFAULT_INSECURE_SECRET)

    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(_env_file=None)


def test_production_refuses_to_start_with_the_env_example_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # El placeholder que trae .env.example es distinto del valor por defecto
    # del código, así que se comprueba también.
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "cambia-esto-por-una-clave-larga-y-aleatoria")

    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(_env_file=None)


def test_production_refuses_a_secret_that_is_too_short(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "corta")

    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(_env_file=None)


def test_production_accepts_a_real_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", secrets.token_urlsafe(48))

    assert Settings(_env_file=None).ENVIRONMENT == "production"


def test_local_development_tolerates_the_default_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # En local se debe poder arrancar sin configurar nada; la comprobación
    # solo aplica a producción.
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.delenv("SECRET_KEY", raising=False)

    assert Settings(_env_file=None).SECRET_KEY == DEFAULT_INSECURE_SECRET
