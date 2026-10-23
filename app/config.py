"""Ajustes de la aplicación, leídos de variables de entorno o de un fichero .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="BIBLIOTECA_")

    # Se puede cambiar a PostgreSQL sin tocar el código: postgresql+psycopg://...
    database_url: str = "sqlite:///biblioteca.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
