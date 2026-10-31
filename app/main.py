"""Punto de entrada: `uv run fastapi dev app/main.py`."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from app.routers import api, pages
from app.templating import templates

app = FastAPI(title="Biblioteca Digital")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.include_router(pages.router)
app.include_router(api.router)


@app.exception_handler(HTTPException)
async def html_not_found(request: Request, exc: HTTPException):
    """Un 404 en una página se muestra como página; en /api sigue siendo JSON."""
    if exc.status_code == 404 and not request.url.path.startswith("/api"):
        # "Not Found" es el texto por defecto de FastAPI para una ruta que no existe.
        detail = "Esta página no existe." if exc.detail == "Not Found" else exc.detail
        return templates.TemplateResponse(request, "404.html", {"detail": detail}, status_code=404)
    return await http_exception_handler(request, exc)
