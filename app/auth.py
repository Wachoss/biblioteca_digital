"""Inicio de sesión del único dueño de la biblioteca.

No hay tabla de usuarios: la contraseña del dueño vive como hash Argon2 en la
configuración (.env) y la sesión es una cookie firmada por `SessionMiddleware`.
La cookie va firmada pero no cifrada (cualquiera puede leerla en base64), así que
solo guarda una huella del hash, nunca nada secreto.

Para generar el hash y la clave de la cookie: `uv run python -m app.auth`.
"""

import hashlib
import secrets
import time
from collections import defaultdict, deque
from getpass import getpass
from typing import Annotated
from urllib.parse import quote

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, Request

from app.config import get_settings

SESSION_KEY = "owner"

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def _fingerprint(password_hash: str) -> str:
    """Lo que se guarda en la cookie. Si cambias la contraseña, cambia la huella y todas
    las sesiones abiertas (por ejemplo, la de un móvil perdido) dejan de valer."""
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def login_enabled() -> bool:
    return bool(get_settings().owner_password_hash)


def check_password(password: str) -> bool:
    password_hash = get_settings().owner_password_hash
    return bool(password_hash) and verify_password(password, password_hash)


def log_in(request: Request) -> None:
    # Se vacía la sesión antes de marcarla: nada de lo que hubiera antes sobrevive al login.
    request.session.clear()
    request.session[SESSION_KEY] = _fingerprint(get_settings().owner_password_hash)


def log_out(request: Request) -> None:
    request.session.clear()


def is_owner(request: Request) -> bool:
    password_hash = get_settings().owner_password_hash
    if not password_hash:
        return False
    stored = request.session.get(SESSION_KEY)
    return isinstance(stored, str) and secrets.compare_digest(stored, _fingerprint(password_hash))


class LoginRequired(Exception):
    """Se lanza desde `require_owner`; `main.py` la convierte en 401 o en redirección."""


def require_owner(request: Request) -> None:
    """Dependencia para toda ruta que añada, edite o borre (hito 4)."""
    if not is_owner(request):
        raise LoginRequired


OwnerDep = Annotated[None, Depends(require_owner)]


def login_url(next_path: str) -> str:
    return f"/entrar?next={quote(next_path, safe='/')}"


def safe_next(next_path: str | None) -> str:
    """Solo se vuelve a rutas de esta misma web: `//otra.web` o `https://…` irían fuera
    (una redirección abierta que se podría usar para phishing)."""
    if next_path and next_path.startswith("/") and not next_path.startswith(("//", "/\\")):
        return next_path
    return "/"


class LoginThrottle:
    """Frena la fuerza bruta: como mucho `max_failures` fallos por IP en `window` segundos.

    Vive en memoria, así que se reinicia con el servidor y no se comparte entre procesos.
    Para un servidor con un solo proceso basta; con varios, haría falta guardarlo en la BD.
    """

    def __init__(self, max_failures: int = 5, window: float = 15 * 60) -> None:
        self.max_failures = max_failures
        self.window = window
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _recent(self, key: str) -> deque[float]:
        failures = self._failures[key]
        while failures and failures[0] <= time.monotonic() - self.window:
            failures.popleft()
        return failures

    def blocked(self, key: str) -> bool:
        return len(self._recent(key)) >= self.max_failures

    def fail(self, key: str) -> None:
        self._recent(key).append(time.monotonic())

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self._failures.clear()
        else:
            self._failures.pop(key, None)


throttle = LoginThrottle()


def main() -> None:
    """Pide la contraseña dos veces e imprime las líneas que hay que pegar en el .env."""
    password = getpass("Contraseña del dueño: ")
    if len(password) < 12:
        raise SystemExit("Usa al menos 12 caracteres.")
    if getpass("Repítela: ") != password:
        raise SystemExit("No coinciden.")
    print("\nCopia estas líneas en tu .env (las comillas simples son necesarias):\n")
    print(f"BIBLIOTECA_OWNER_PASSWORD_HASH='{hash_password(password)}'")
    if not get_settings().secret_key:
        print(f"BIBLIOTECA_SECRET_KEY='{secrets.token_urlsafe(32)}'")


if __name__ == "__main__":
    main()
