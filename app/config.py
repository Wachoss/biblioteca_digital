"""Ajustes de la aplicación, leídos de variables de entorno o de un fichero .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="BIBLIOTECA_")

    # Se puede cambiar a PostgreSQL sin tocar el código: postgresql+psycopg://...
    database_url: str = "sqlite:///biblioteca.db"

    # Hash Argon2 de la contraseña del dueño; se genera con `uv run python -m app.auth`.
    # Sin él no se puede iniciar sesión y la aplicación es solo de lectura.
    owner_password_hash: str | None = None

    # Clave con la que se firma la cookie de sesión. Si falta, se inventa una al arrancar
    # y las sesiones se pierden en cada reinicio (cómodo en desarrollo, malo en producción).
    secret_key: str | None = None

    # En producción, con HTTPS, debe ser true: el navegador solo enviará la cookie cifrada.
    session_https_only: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
