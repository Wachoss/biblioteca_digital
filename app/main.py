"""Punto de entrada: `uv run uvicorn app.main:app --reload`."""

import logging
import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.auth import LoginRequired, login_url
from app.config import get_settings
from app.routers import api, auth, pages
from app.templating import templates

settings = get_settings()
if not settings.secret_key:
    logging.getLogger(__name__).warning(
        "Falta BIBLIOTECA_SECRET_KEY: las sesiones se perderán al reiniciar el servidor."
    )

app = FastAPI(title="Biblioteca Digital")
# Sesión en una cookie firmada con la clave secreta: si alguien la modifica, la firma
# deja de cuadrar y la sesión se descarta. SameSite=Lax impide que otra web envíe un
# formulario (POST) a esta con la cookie del dueño, que es la defensa contra CSRF.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key or secrets.token_urlsafe(32),
    session_cookie="biblioteca_sesion",
    max_age=30 * 24 * 60 * 60,  # 30 días; en el móvil no apetece escribirla cada día
    same_site="lax",
    https_only=settings.session_https_only,
)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(api.router)


@app.exception_handler(LoginRequired)
async def login_required(request: Request, _exc: LoginRequired):
    """Sin sesión: la API responde 401 y una página manda al formulario de entrada."""
    if request.url.path.startswith("/api"):
        return JSONResponse({"detail": "Hay que iniciar sesión"}, status_code=401)
    next_path = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    # Si la petición viene de HTMX, una redirección normal se cargaría dentro del trozo
    # de página; HX-Redirect le pide que cambie la página entera.
    if "hx-request" in request.headers:
        return Response(status_code=401, headers={"HX-Redirect": login_url(next_path)})
    return RedirectResponse(login_url(next_path), status_code=303)


@app.exception_handler(HTTPException)
async def html_not_found(request: Request, exc: HTTPException):
    """Un 404 en una página se muestra como página; en /api sigue siendo JSON."""
    if exc.status_code == 404 and not request.url.path.startswith("/api"):
        # "Not Found" es el texto por defecto de FastAPI para una ruta que no existe.
        detail = "Esta página no existe." if exc.detail == "Not Found" else exc.detail
        return templates.TemplateResponse(request, "404.html", {"detail": detail}, status_code=404)
    return await http_exception_handler(request, exc)
