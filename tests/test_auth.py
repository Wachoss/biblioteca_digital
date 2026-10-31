import pytest
from fastapi import APIRouter

from app import auth
from app.auth import OwnerDep
from app.main import app

PASSWORD = "una contraseña larga de prueba"
# Calcular un hash Argon2 cuesta a propósito; se hace una sola vez para todos los tests.
PASSWORD_HASH = auth.hash_password(PASSWORD)


@pytest.fixture(autouse=True)
def owner_configured(monkeypatch):
    monkeypatch.setenv("BIBLIOTECA_OWNER_PASSWORD_HASH", PASSWORD_HASH)
    auth.get_settings.cache_clear()
    auth.throttle.reset()
    yield
    auth.get_settings.cache_clear()


@pytest.fixture
def protected_routes():
    """Rutas de escritura de mentira hasta que existan las de verdad (hito 4)."""
    router = APIRouter()

    @router.post("/libros/nuevo")
    def new_book_page(_owner: OwnerDep):
        return {"ok": True}

    @router.delete("/api/books/{book_id}")
    def delete_book(_owner: OwnerDep, book_id: int):
        return {"deleted": book_id}

    before = len(app.router.routes)
    app.include_router(router)
    yield
    del app.router.routes[before:]


def log_in(client, password=PASSWORD, next_path="/"):
    return client.post(
        "/entrar", data={"password": password, "next": next_path}, follow_redirects=False
    )


def test_login_with_right_password_redirects_to_next(client):
    response = log_in(client, next_path="/libros/1")
    assert response.status_code == 303
    assert response.headers["location"] == "/libros/1"
    assert "biblioteca_sesion" in response.cookies
    assert "Has iniciado sesión" in client.get("/").text


def test_login_with_wrong_password_fails(client):
    response = log_in(client, password="no es esta")
    assert response.status_code == 401
    assert "Contraseña incorrecta" in response.text
    assert "Has iniciado sesión" not in client.get("/").text


@pytest.mark.parametrize("target", ["https://malo.example", "//malo.example", "/\\malo.example"])
def test_login_never_redirects_outside(client, target):
    assert log_in(client, next_path=target).headers["location"] == "/"


def test_logout(client):
    log_in(client)
    response = client.post("/salir", follow_redirects=False)
    assert response.status_code == 303
    assert "Has iniciado sesión" not in client.get("/").text


def test_too_many_failures_block_even_the_right_password(client):
    for _ in range(auth.throttle.max_failures):
        log_in(client, password="mal")
    response = log_in(client)
    assert response.status_code == 429
    assert "Demasiados intentos" in response.text


def test_changing_password_ends_open_sessions(client, monkeypatch):
    log_in(client)
    monkeypatch.setenv("BIBLIOTECA_OWNER_PASSWORD_HASH", auth.hash_password("otra contraseña"))
    auth.get_settings.cache_clear()
    assert "Has iniciado sesión" not in client.get("/").text


def test_without_configured_password_login_is_disabled(client, monkeypatch):
    monkeypatch.delenv("BIBLIOTECA_OWNER_PASSWORD_HASH")
    auth.get_settings.cache_clear()
    assert "no está configurado" in client.get("/entrar").text
    assert log_in(client).status_code == 401


def test_catalog_stays_public(client):
    assert client.get("/").status_code == 200
    assert client.get("/api/books").status_code == 200


def test_protected_page_redirects_to_login(client, protected_routes):
    response = client.post("/libros/nuevo", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/entrar?next=/libros/nuevo"


def test_protected_page_from_htmx_asks_for_full_redirect(client, protected_routes):
    response = client.post("/libros/nuevo", headers={"HX-Request": "true"})
    assert response.status_code == 401
    assert response.headers["hx-redirect"] == "/entrar?next=/libros/nuevo"


def test_protected_api_returns_401(client, protected_routes):
    response = client.delete("/api/books/1")
    assert response.status_code == 401
    assert response.json() == {"detail": "Hay que iniciar sesión"}


def test_owner_can_use_protected_routes(client, protected_routes):
    log_in(client)
    assert client.post("/libros/nuevo").json() == {"ok": True}
    assert client.delete("/api/books/1").json() == {"deleted": 1}


def test_tampered_cookie_is_ignored(client):
    log_in(client)
    value = client.cookies["biblioteca_sesion"]
    client.cookies.set("biblioteca_sesion", value[:-2] + ("AA" if value[-2:] != "AA" else "BB"))
    assert "Has iniciado sesión" not in client.get("/").text


def test_throttle_forgets_old_failures(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(auth.time, "monotonic", lambda: clock[0])
    throttle = auth.LoginThrottle(max_failures=2, window=60)
    throttle.fail("ip")
    throttle.fail("ip")
    assert throttle.blocked("ip")
    clock[0] += 61
    assert not throttle.blocked("ip")
