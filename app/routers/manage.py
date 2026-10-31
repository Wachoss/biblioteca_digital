"""Páginas del dueño para añadir, editar y borrar libros.

La protección va en el router entero (`dependencies=[...]`) y no ruta a ruta: así una
ruta nueva que se añada aquí no puede quedarse abierta por olvido.

Todas las escrituras son formularios HTML con POST y no DELETE o PUT, porque un
formulario sin JavaScript solo sabe hacer GET y POST. La protección contra CSRF la da
la cookie de sesión con SameSite=Lax (ver `main.py`).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import require_owner
from app.db import SessionDep
from app.isbn import normalize_isbn
from app.models import Book
from app.services import books, catalog
from app.services.openlibrary import OpenLibrary, OpenLibraryError, get_openlibrary
from app.templating import templates

router = APIRouter(include_in_schema=False, dependencies=[Depends(require_owner)])

OpenLibraryDep = Annotated[OpenLibrary, Depends(get_openlibrary)]


def _form(request: Request, book: Book | None, status_code: int = 200, **context):
    context.setdefault("values", {})
    context.setdefault("errors", {})
    context["book"] = book
    return templates.TemplateResponse(request, "book_form.html", context, status_code=status_code)


def _get_book_or_404(session: SessionDep, book_id: int) -> Book:
    book = catalog.get_book(session, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    return book


@router.get("/libros/nuevo", response_class=HTMLResponse)
def new_book_page(request: Request, session: SessionDep, ol: OpenLibraryDep, isbn: str = ""):
    """Formulario de alta. Con `?isbn=` busca antes en Open Library y lo rellena.

    Buscar es un GET porque no cambia nada: la URL se puede recargar o compartir, y
    funciona sin JavaScript. Los datos encontrados no se guardan todavía; primero se
    enseñan para revisarlos, porque Open Library a veces trae títulos en otro idioma
    o mezcla traductores con autores (lo vimos con el Excel).
    """
    if not isbn.strip():
        return _form(request, None)
    lookup = {"isbn": isbn}
    isbn13 = normalize_isbn(isbn)
    if isbn13 is None:
        return _form(request, None, 422, lookup=lookup, lookup_error="No es un ISBN válido.")
    if existing := books.find_by_isbn(session, isbn13):
        return _form(request, None, lookup=lookup, existing=existing)
    values = {"isbn": isbn13}
    try:
        found = ol.lookup_isbn(isbn13)
    except OpenLibraryError:
        notice = "No se ha podido consultar Open Library. Puedes rellenar los datos a mano."
        return _form(request, None, lookup=lookup, values=values, notice=notice)
    if found is None:
        notice = "Open Library no tiene este ISBN. Rellena los datos a mano."
        return _form(request, None, lookup=lookup, values=values, notice=notice)
    values |= {
        "title": found.title,
        "authors": "\n".join(found.authors),
        "publish_year": str(found.publish_year or ""),
        "cover_url": found.cover_url or "",
        "openlibrary_key": found.openlibrary_key or "",
    }
    notice = "Datos de Open Library. Revísalos antes de guardar."
    return _form(request, None, lookup=lookup, values=values, notice=notice, found=True)


async def _form_data(request: Request) -> dict[str, str]:
    form = await request.form()
    return {k: v for k, v in form.items() if isinstance(v, str)}


FormDep = Annotated[dict[str, str], Depends(_form_data)]


@router.post("/libros/nuevo", response_class=HTMLResponse)
def create_book(request: Request, session: SessionDep, form: FormDep):
    data, errors = books.parse_book_form(form)
    if data is not None:
        try:
            book = books.create_book(session, data)
        except books.DuplicateIsbn as exc:
            errors = {"isbn": "Ya tienes un libro con este ISBN."}
            return _form(request, None, 409, values=form, errors=errors, existing=exc.book)
        # 303 + GET de la ficha (Post/Redirect/Get): recargar no lo guarda dos veces.
        return RedirectResponse(request.url_for("book_page", book_id=book.id), status_code=303)
    return _form(request, None, 422, values=form, errors=errors)


@router.get("/libros/{book_id}/editar", response_class=HTMLResponse)
def edit_book_page(request: Request, session: SessionDep, book_id: int):
    book = _get_book_or_404(session, book_id)
    return _form(request, book, values=books.form_values(book))


@router.post("/libros/{book_id}/editar", response_class=HTMLResponse)
def update_book(request: Request, session: SessionDep, form: FormDep, book_id: int):
    book = _get_book_or_404(session, book_id)
    data, errors = books.parse_book_form(form)
    if data is not None:
        try:
            books.update_book(session, book, data)
        except books.DuplicateIsbn as exc:
            session.rollback()
            errors = {"isbn": "Ya tienes otro libro con este ISBN."}
            return _form(request, book, 409, values=form, errors=errors, existing=exc.book)
        return RedirectResponse(request.url_for("book_page", book_id=book.id), status_code=303)
    return _form(request, book, 422, values=form, errors=errors)


@router.post("/libros/{book_id}/borrar")
def delete_book(request: Request, session: SessionDep, book_id: int):
    books.delete_book(session, _get_book_or_404(session, book_id))
    return RedirectResponse(request.url_for("catalog_page"), status_code=303)
