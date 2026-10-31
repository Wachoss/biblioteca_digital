"""La parte de PWA: manifest, service worker, página sin conexión y favicon."""

import re

from app.routers import pwa


def test_manifest_is_installable(client):
    response = client.get("/manifest.webmanifest")
    assert response.headers["content-type"] == "application/manifest+json"
    manifest = response.json()
    # Lo mínimo que piden los navegadores para ofrecer "Instalar".
    assert manifest["name"] and manifest["short_name"]
    assert manifest["start_url"] == "/"
    assert manifest["display"] == "standalone"
    sizes = {icon["sizes"] for icon in manifest["icons"]}
    assert {"192x192", "512x512"} <= sizes
    assert any(icon["purpose"] == "maskable" for icon in manifest["icons"])


def test_manifest_icons_exist(client):
    manifest = client.get("/manifest.webmanifest").json()
    icons = manifest["icons"] + manifest["shortcuts"][0]["icons"]
    for icon in icons:
        response = client.get(icon["src"])
        assert response.status_code == 200, icon["src"]
        assert response.headers["content-type"] == "image/png"


def test_pages_link_manifest_and_icons(client):
    html = client.get("/").text
    assert '<link rel="manifest" href="/manifest.webmanifest">' in html
    assert "apple-touch-icon.png" in html
    assert "/static/app.js" in html


def test_favicon(client):
    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/x-icon"


def test_service_worker_is_served_from_root_without_cache(client):
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/javascript")
    assert response.headers["cache-control"] == "no-cache"
    assert f'const VERSION = "{pwa.assets_version()}";' in response.text


def test_service_worker_precaches_existing_files(client):
    text = client.get("/sw.js").text
    precache = re.search(r"const PRECACHE = (\[.*?\]);", text).group(1)
    urls = re.findall(r'"([^"]+)"', precache)
    assert "/sin-conexion" in urls
    for url in urls:
        assert client.get(url).status_code == 200, url


def test_assets_version_changes_with_static_files(monkeypatch, tmp_path):
    (tmp_path / "style.css").write_text("a {}")
    monkeypatch.setattr(pwa, "STATIC_DIR", tmp_path)
    pwa.assets_version.cache_clear()
    before = pwa.assets_version()
    (tmp_path / "style.css").write_text("a { color: red }")
    pwa.assets_version.cache_clear()
    assert pwa.assets_version() != before
    pwa.assets_version.cache_clear()


def test_offline_page_hides_session_controls(owner):
    html = owner.get("/sin-conexion").text
    assert "Sin conexión" in html
    # Aunque la pida el dueño, la copia guardada no debe enseñar sus botones.
    assert "Añadir libro" not in html
    assert "Salir" not in html
    assert "Añadir libro" in owner.get("/").text
