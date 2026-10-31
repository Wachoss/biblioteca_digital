"""Páginas HTML. Cada ruta devuelve la página entera o, si la pide HTMX, solo un trozo."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.db import SessionDep
from app.models import ReadingStatus
from app.services import catalog
from app.templating import templates

router = APIRouter(include_in_schema=False)


def parse_status(value: str) -> ReadingStatus | None:
    """En las páginas, un estado vacío ("Todos") o inválido simplemente no filtra.

    Por eso no se declara el parámetro como `ReadingStatus | None`: FastAPI respondería
    422 al ver `?status=`, que es justo lo que envía el botón "Todos" del formulario.
    """
    try:
        return ReadingStatus(value)
    except ValueError:
        return None


def is_htmx_fragment(request: Request) -> bool:
    # HTMX añade HX-Request a sus peticiones. Al volver atrás en el navegador puede pedir
    # la página completa (HX-History-Restore-Request) y entonces hay que darle la entera.
    headers = request.headers
    return "hx-request" in headers and "hx-history-restore-request" not in headers


@router.get("/", response_class=HTMLResponse)
def catalog_page(request: Request, session: SessionDep, q: str = "", status: str = ""):
    selected = parse_status(status)
    context = {
        "books": catalog.search_books(session, q, selected),
        "q": q,
        "selected": selected,
    }
    if is_htmx_fragment(request):
        response = templates.TemplateResponse(request, "_results.html", context)
    else:
        context["counts"] = catalog.count_by_status(session)
        response = templates.TemplateResponse(request, "catalog.html", context)
    # La misma URL devuelve dos respuestas distintas según la cabecera: avisa a las cachés.
    response.headers["Vary"] = "HX-Request"
    return response


@router.get("/libros/{book_id}", response_class=HTMLResponse)
def book_page(request: Request, session: SessionDep, book_id: int):
    book = catalog.get_book(session, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    return templates.TemplateResponse(request, "book.html", {"book": book})
