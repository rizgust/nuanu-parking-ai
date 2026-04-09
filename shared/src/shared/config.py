"""Base settings for all services using Pydantic Settings v2.

Each service subclasses BaseServiceSettings and adds service-specific fields.
All values are read from environment variables (or .env file via Docker).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    """Common settings shared across all services."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore env vars not declared in this model
    )

    mqtt_host: str = "mosquitto"
    mqtt_port: int = 1883
    log_level: str = "INFO"
