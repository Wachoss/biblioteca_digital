"""El escáner de ISBN: que la página lo cargue bien y que sus ficheros existan.

La lógica del escáner es JavaScript y aquí no se ejecuta (para eso haría falta un
navegador); lo que sí se comprueba es lo que podría romperse en el lado de Python:
que el HTML lleve lo que scanner.js busca y que las librerías se sirvan bien.
"""

import hashlib
import re

from app.routers.pwa import STATIC_DIR


def _scanner_script(html):
    return re.search(r'<script src="[^"]*/static/scanner\.js"[^>]*>', html, re.S)


def test_new_book_page_loads_scanner(owner):
    html = owner.get("/libros/nuevo").text
    assert "data-isbn-lookup" in html
    # El botón empieza oculto: sin JavaScript (o sin cámara) no debe aparecer.
    assert re.search(r"<button[^>]*data-scan\b[^>]*\bhidden\b", html, re.S)
    assert 'capture="environment"' in html
    assert '<dialog id="escaner"' in html
    assert _scanner_script(html)


def test_scanner_library_urls_exist(owner):
    tag = _scanner_script(owner.get("/libros/nuevo").text).group(0)
    ponyfill = re.search(r'data-ponyfill="([^"]+)"', tag).group(1)
    wasm = re.search(r'data-wasm="([^"]+)"', tag).group(1)
    assert owner.get(ponyfill).status_code == 200
    response = owner.get(wasm)
    assert response.status_code == 200
    # Con este tipo el navegador compila el WebAssembly mientras lo descarga.
    assert response.headers["content-type"] == "application/wasm"


def test_vendored_wasm_matches_the_library_version():
    # La librería lleva dentro la huella del .wasm con el que se probó. Si se actualiza
    # una sin la otra, este test lo dice antes de que falle en el móvil.
    vendor = STATIC_DIR / "vendor"
    [ponyfill] = vendor.glob("barcode-detector-*-ponyfill.js")
    [wasm] = vendor.glob("zxing-reader-*.wasm")
    sha256 = hashlib.sha256(wasm.read_bytes()).hexdigest()
    assert sha256 in ponyfill.read_text()


def test_edit_page_does_not_load_scanner(owner, session):
    html = owner.get("/libros/1/editar").text
    assert not _scanner_script(html)
    assert "data-scan" not in html


def test_public_pages_do_not_load_scanner(client):
    assert not _scanner_script(client.get("/").text)
