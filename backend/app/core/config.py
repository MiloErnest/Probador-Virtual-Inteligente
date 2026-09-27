"""Configuración de la aplicación.

Toda la configuración se lee de variables de entorno (o del archivo `.env`).
Ningún secreto vive en el código fuente (Regla 9).

`Settings` es la única fuente de verdad: si un módulo necesita un valor
configurable, lo pide aquí en lugar de leer `os.environ` por su cuenta.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# backend/app/core/config.py -> parents[0]=core, [1]=app, [2]=backend
BACKEND_DIR = Path(__file__).resolve().parents[2]

# Valor centinela de SECRET_KEY. Permite arrancar en local sin configurar
# nada, pero se rechaza explícitamente en producción (ver el validador de
# más abajo): con esta clave conocida, cualquiera puede firmar un token
# válido para cualquier usuario.
DEFAULT_INSECURE_SECRET = "clave-insegura-solo-para-desarrollo"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Aplicación ---
    PROJECT_NAME: str = "Probador Virtual Inteligente"
    VERSION: str = "0.1.0"
    API_PREFIX: str = "/api"
    ENVIRONMENT: Literal["local", "test", "production"] = "local"
    DEBUG: bool = True

    # --- Seguridad ---
    # Firma los tokens JWT. Cambiarla invalida todas las sesiones abiertas.
    SECRET_KEY: str = DEFAULT_INSECURE_SECRET

    # Duración del token de acceso. No hay refresh token ni lista de
    # revocación (Etapa 2): un valor muy alto alarga la ventana en la que un
    # token robado sigue sirviendo, y uno muy bajo obliga a reidentificarse a
    # media sesión. 12 horas cubre una jornada de trabajo del proyecto.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720

    # --- Base de datos ---
    DATABASE_URL: str = "postgresql+psycopg://vfit:vfit_dev_password@localhost:5432/vfit"

    # --- CORS ---
    # `NoDecode` desactiva el parseo JSON automático que pydantic-settings
    # aplica a los campos de tipo complejo. Sin él, el valor del .env se
    # intenta leer como JSON ANTES de que corra el validador de abajo, y una
    # lista separada por comas revienta con SettingsError.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # --- Almacenamiento de imágenes ---
    STORAGE_DIR: Path = BACKEND_DIR / "storage"
    MEDIA_URL_PATH: str = "/media"
    PUBLIC_BASE_URL: str = "http://localhost:8000"
    MAX_UPLOAD_MB: int = 8

    # --- Motor generativo para bocetos ---
    #
    # "none"   = no hay motor de IA. Los bocetos no se pueden vestir y se dice
    #            por qué. Es el valor por defecto A PROPÓSITO: que clonar el
    #            repositorio empiece a gastar dinero de alguien sería una
    #            trampa.
    # "openai" = API de OpenAI. SE COBRA POR IMAGEN.
    #
    # Un valor desconocido hace fallar el procesado, nunca cae al motor
    # determinista en silencio. Creer que estás usando la IA cuando en realidad
    # estás multiplicando píxeles sería el peor error posible aquí, y ya se
    # cometió una vez en este proyecto.
    AI_PROVIDER: str = "none"

    #: Se obtiene en https://platform.openai.com/api-keys
    #: NUNCA en el código: este campo se lee del .env, que está en .gitignore.
    OPENAI_API_KEY: str = ""

    # Modelo de imagen para el camino de EDICIÓN de prenda. Configurable porque
    # este catálogo se mueve deprisa y los precios cambian con él.
    #
    # Estuvo en `gpt-image-1-mini` y era un error medido: de los ocho modelos
    # que acepta `images.edit` (dall-e-2, gpt-image-1, gpt-image-1-mini,
    # gpt-image-1.5, gpt-image-2, gpt-image-2-2026-04-21, gpt-image-2.5-sunburst
    # y gpt-image-2.5-flare) era el más débil, y además **el único que rechaza
    # `input_fidelity`**. Como ese 400 se reintenta sin el parámetro, todas las
    # llamadas salían con la fidelidad DESACTIVADA sin que se notara.
    OPENAI_IMAGE_MODEL: str = "gpt-image-2.5-sunburst"

    # Calidad de la edición. Se cobra por píxel generado, así que subirla cuesta;
    # pero con una tela lo que se está mirando ES el detalle fino, y en "auto"
    # el modelo puede elegir una calidad que borra justo eso.
    OPENAI_IMAGE_QUALITY: str = "high"

    # Modelo para sintetizar el MOSAICO de una tela (`app/textil/tejido_ia.py`).
    # Se separa del anterior a propósito: son dos trabajos distintos y conviene
    # poder pagarlos distinto. Éste se ejecuta una vez por tela y para siempre.
    OPENAI_TEXTURE_MODEL: str = "gpt-image-2.5-sunburst"

    # Calidad del mosaico. Aquí sí compensa la alta: el mosaico se genera una
    # sola vez por tela y después lo usan todas las pruebas de todos los
    # usuarios. Es el único sitio del proyecto donde el gasto no se repite.
    OPENAI_TEXTURE_QUALITY: str = "high"

    # `input_fidelity="high"` le dice al modelo que respete el detalle de la
    # imagen de entrada. Es la diferencia entre «tu diseño con otra tela» y
    # «un diseño parecido al tuyo»: sin esto, el modelo mueve los botones,
    # cambia el cuello y reinventa el corte, que es justo lo contrario de lo
    # que le pide una modista.
    OPENAI_INPUT_FIDELITY: Literal["high", "low"] = "high"

    # Corte de la llamada. Debe ser MENOR que el corte del sondeo del navegador
    # (120 s en el frontend); si no, el navegador se rinde antes de que la
    # prueba termine y el usuario no llega a ver el resultado.
    OPENAI_TIMEOUT_SECONDS: int = 100

    # TECHO DE GASTO, EN LA APLICACIÓN Y NO SOLO EN EL PANEL DE OPENAI
    #
    # El límite de la cuenta protege la cartera; este protege al usuario de que
    # un fallo suyo —o un bucle en el frontend— se coma el presupuesto de
    # todos. Se cuenta por usuario y día natural.
    AI_TRIALS_PER_USER_PER_DAY: int = 20

    # --- Probador: la persona de la foto con la prenda puesta ---
    #
    # "fashn" = FASHN VTON 1.5 en su Space de Hugging Face. GRATUITO, con la
    #           cuota diaria de ZeroGPU. Por eso es el valor por defecto, al
    #           revés que AI_PROVIDER: aquí clonar el repositorio no le cuesta
    #           dinero a nadie. Lo que sí hace es mandar la foto a Hugging
    #           Face, y la interfaz lo dice antes de subirla.
    # "none"  = sin probador; la prueba falla diciendo cómo activarlo.
    VTO_PROVIDER: str = "fashn"

    #: La dirección DIRECTA del Space `fashn-ai/fashn-vton-1.5`, no su nombre.
    #: Con el nombre, el cliente pregunta antes a la API de huggingface.co
    #: dónde está, y en el equipo de desarrollo esa pregunta tardaba 168 s
    #: —huggingface.co anuncia IPv6, la red no lo encamina, y Python espera a
    #: que caduque antes de probar IPv4—, mientras el Space respondía en 0,6 s.
    #: Con la dirección no hay pregunta, y el token se sigue enviando.
    VTO_SPACE: str = "https://fashn-ai-fashn-vton-1-5.hf.space"

    #: Token de LECTURA de una cuenta gratuita de Hugging Face. Opcional: sin
    #: él, la cuota de ZeroGPU se agota en unas dos pruebas al día. Se crea en
    #: https://huggingface.co/settings/tokens y va en el .env, nunca en código.
    HF_TOKEN: str = ""

    #: Pasos del modelo (10–50). Medido: 30 pasos, unos 28 s por prueba.
    VTO_STEPS: int = 30
    VTO_TIMEOUT_SECONDS: int = 240

    #: Lado mayor con que se guarda la foto de una persona. Por encima, el
    #: modelo no aporta más detalle, y una foto de 12 megapíxeles de alguien
    #: no tiene por qué quedarse en el servidor a tamaño completo.
    PERSON_PHOTO_MAX_SIDE: int = 2048

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """CORS_ORIGINS se escribe como lista separada por comas en el .env.

        El formato JSON (`["http://a", "http://b"]`) NO está soportado: al
        desactivar el decodificador con `NoDecode`, aquí llega siempre la
        cadena en bruto.
        """
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _reject_insecure_secret_in_production(self) -> "Settings":
        """Impide desplegar en producción con la clave de ejemplo.

        Se falla al arrancar, no en la primera petición: un backend que firma
        tokens con una clave pública no es un backend degradado, es un backend
        sin autenticación. Mejor que no arranque a que parezca que funciona.
        """
        if self.ENVIRONMENT != "production":
            return self

        placeholders = {
            DEFAULT_INSECURE_SECRET,
            "cambia-esto-por-una-clave-larga-y-aleatoria",
        }
        if self.SECRET_KEY in placeholders or len(self.SECRET_KEY) < 32:
            raise ValueError(
                "SECRET_KEY sigue siendo un valor de ejemplo o es demasiado corta "
                "y ENVIRONMENT=production. Genera una clave real con:\n"
                '  python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return self

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Instancia cacheada: el .env se lee una sola vez por proceso."""
    return Settings()


settings = get_settings()
