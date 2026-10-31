"""Utilidades compartidas por los tests."""

from app import auth

PASSWORD = "una contraseña larga de prueba"
# Calcular un hash Argon2 cuesta a propósito; se hace una sola vez para todos los tests.
PASSWORD_HASH = auth.hash_password(PASSWORD)


def log_in(client, password=PASSWORD, next_path="/"):
    return client.post(
        "/entrar", data={"password": password, "next": next_path}, follow_redirects=False
    )
