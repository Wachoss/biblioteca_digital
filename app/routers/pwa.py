"""Lo que convierte la web en una aplicación instalable (PWA).

- `/manifest.webmanifest`: nombre, iconos y colores con los que se instala.
- `/sw.js`: el service worker, que guarda una copia de la web para usarla sin conexión.
- `/sin-conexion`: la página que enseña el service worker cuando no tiene otra cosa.
- `/favicon.ico`: los navegadores lo piden en la raíz aunque la página no lo enlace.

El manifest y el service worker se sirven desde rutas y no como ficheros estáticos:
el service worker solo puede controlar las URL que cuelgan de la carpeta desde la que
se sirve, así que en /static/sw.js solo controlaría /static/. Además, al generarlo
aquí se le puede poner una versión calculada sola (ver `assets_version`).
"""

import hashlib
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.templating import templates

router = APIRouter(include_in_schema=False)

APP_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = APP_DIR / "static"
ICONS_DIR = STATIC_DIR / "icons"

# Azul de Pico.css: la barra de estado y la pantalla de carga de la app instalada.
BRAND_COLOR = "#0172ad"

# Ficheros que el service worker descarga al instalarse para poder pintar cualquier
# página sin conexión. Las portadas no van aquí: vienen de Open Library (ver sw.js).
PRECACHE_STATIC = [
    "vendor/pico-2.1.1.min.css",
    "vendor/htmx-2.0.11.min.js",
    "style.css",
    "app.js",
    "icons/icon-192.png",
]


@lru_cache
def assets_version() -> str:
    """Huella de los ficheros estáticos y las plantillas.

    Va dentro de sw.js, así que si cambia cualquier CSS, JS o plantilla, cambia sw.js;
    el navegador detecta que es otro, instala el nuevo y este descarta las cachés
    viejas. Sin esto habría que acordarse de subir una versión a mano en cada cambio.
    """
    digest = hashlib.sha256()
    for folder in (STATIC_DIR, APP_DIR / "templates"):
        for path in sorted(p for p in folder.rglob("*") if p.is_file()):
            digest.update(path.relative_to(folder).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


@router.get("/manifest.webmanifest")
def manifest(request: Request):
    def icon(name: str, size: int, purpose: str = "any") -> dict:
        src = request.url_for("static", path=f"icons/{name}").path
        return {"src": src, "sizes": f"{size}x{size}", "type": "image/png", "purpose": purpose}

    data = {
        "id": "/",
        "name": "Biblioteca Digital",
        "short_name": "Biblioteca",
        "description": "Catálogo personal de libros",
        "lang": "es",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": BRAND_COLOR,
        "theme_color": BRAND_COLOR,
        "icons": [
            icon("icon-192.png", 192),
            icon("icon-512.png", 512),
            icon("icon-maskable-512.png", 512, "maskable"),
        ],
        # Pulsación larga sobre el icono instalado: acceso directo al alta de libros.
        "shortcuts": [
            {
                "name": "Añadir libro",
                "url": request.url_for("new_book_page").path,
                "icons": [icon("icon-192.png", 192)],
            }
        ],
    }
    return JSONResponse(data, media_type="application/manifest+json")


@router.get("/sw.js")
def service_worker(request: Request):
    context = {
        "version": assets_version(),
        "offline_url": request.url_for("offline_page").path,
        "precache": [request.url_for("static", path=p).path for p in PRECACHE_STATIC],
    }
    response = templates.TemplateResponse(request, "sw.js", context, media_type="text/javascript")
    # Que el navegador pregunte siempre si hay versión nueva en vez de fiarse de su caché.
    response.headers["Cache-Control"] = "no-cache"
    return response


@router.get("/sin-conexion", response_class=HTMLResponse)
def offline_page(request: Request):
    # `offline` oculta lo que depende de la sesión (botones del dueño, Entrar/Salir):
    # esta página se guarda una vez y se enseña a quien sea, con o sin sesión.
    return templates.TemplateResponse(request, "offline.html", {"offline": True})


@router.get("/favicon.ico")
def favicon():
    return FileResponse(ICONS_DIR / "favicon.ico", media_type="image/x-icon")
