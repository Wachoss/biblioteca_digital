"""Entrar y salir. Solo hay un usuario, así que el formulario pide solo la contraseña."""

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import auth
from app.templating import templates

router = APIRouter(include_in_schema=False)


def _form(request: Request, next_path: str, error: str | None = None, status_code: int = 200):
    context = {"next": next_path, "error": error, "enabled": auth.login_enabled()}
    return templates.TemplateResponse(request, "login.html", context, status_code=status_code)


@router.get("/entrar", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/"):
    next_path = auth.safe_next(next)
    if auth.is_owner(request):
        return RedirectResponse(next_path, status_code=303)
    return _form(request, next_path)


@router.post("/entrar", response_class=HTMLResponse)
def login(
    request: Request,
    password: Annotated[str, Form()] = "",
    next: Annotated[str, Form()] = "/",
):
    next_path = auth.safe_next(next)
    client = request.client.host if request.client else "desconocido"
    if auth.throttle.blocked(client):
        error = "Demasiados intentos fallidos. Espera unos minutos y vuelve a probar."
        return _form(request, next_path, error, status_code=429)
    if not auth.check_password(password):
        auth.throttle.fail(client)
        return _form(request, next_path, "Contraseña incorrecta.", status_code=401)
    auth.throttle.reset(client)
    auth.log_in(request)
    # 303: tras un POST, el navegador hace GET a la nueva URL (patrón Post/Redirect/Get).
    return RedirectResponse(next_path, status_code=303)


@router.post("/salir")
def logout(request: Request):
    # Salir es POST y no un enlace: un GET lo podría disparar cualquier web ajena
    # con una simple <img src="…/salir">.
    auth.log_out(request)
    return RedirectResponse("/", status_code=303)
