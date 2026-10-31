import pytest

from app import auth
from tests.helpers import log_in


@pytest.fixture(autouse=True)
def _owner(owner_configured):
    """En todos los tests de este fichero hay contraseña configurada."""


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


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/libros/nuevo"),
        ("post", "/libros/nuevo"),
        ("get", "/libros/1/editar"),
        ("post", "/libros/1/editar"),
        ("post", "/libros/1/borrar"),
    ],
)
def test_write_routes_redirect_to_login(client, method, path):
    response = client.request(method, path, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/entrar?next={path}"


def test_protected_page_from_htmx_asks_for_full_redirect(client):
    response = client.get("/libros/nuevo", headers={"HX-Request": "true"})
    assert response.status_code == 401
    assert response.headers["hx-redirect"] == "/entrar?next=/libros/nuevo"


def test_anonymous_cannot_delete(client):
    client.post("/libros/1/borrar")
    assert client.get("/libros/1").status_code == 200


def test_owner_sees_write_links(client):
    assert "Añadir libro" not in client.get("/").text
    log_in(client)
    assert "Añadir libro" in client.get("/").text
    assert "Editar" in client.get("/libros/1").text


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
