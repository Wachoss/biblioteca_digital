"""Añadir, editar y borrar libros. Como `catalog.py`, no sabe nada de HTTP."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.isbn import normalize_isbn
from app.models import Author, Book, ReadingStatus
from app.text import clean, fold


@dataclass
class BookInput:
    """Los datos de un libro ya validados, listos para guardar."""

    title: str
    authors: list[str]
    status: ReadingStatus
    isbn13: str | None
    publish_year: int | None
    cover_url: str | None
    openlibrary_key: str | None
    notes: str | None


FORM_FIELDS = ("title", "authors", "status", "isbn", "publish_year", "cover_url", "notes")


def parse_book_form(form: Mapping[str, str]) -> tuple[BookInput | None, dict[str, str]]:
    """Valida el formulario. Devuelve (datos, {}) o (None, {campo: mensaje de error}).

    Se valida a mano y no con un modelo de Pydantic porque, si algo falla, hay que volver
    a pintar el formulario con lo que se escribió y un mensaje junto a cada campo; FastAPI
    con Pydantic respondería un 422 en JSON, que en una página no sirve.
    """
    errors: dict[str, str] = {}

    title = clean(form.get("title"))
    if not title:
        errors["title"] = "El título es obligatorio."
    elif len(title) > 300:
        errors["title"] = "Como mucho 300 caracteres."

    # Un autor por línea: las comas no sirven de separador porque hay nombres como
    # "Tolkien, J. R. R." o "Martin Luther King, Jr.".
    authors: list[str] = []
    for line in (form.get("authors") or "").splitlines():
        name = clean(line)
        if name and fold(name) not in {fold(a) for a in authors}:
            authors.append(name)
    if any(len(a) > 200 for a in authors):
        errors["authors"] = "Cada nombre, como mucho 200 caracteres."

    try:
        status = ReadingStatus(form.get("status") or ReadingStatus.PENDING)
    except ValueError:
        errors["status"] = "Estado desconocido."
        status = ReadingStatus.PENDING

    isbn13 = None
    if raw_isbn := clean(form.get("isbn")):
        isbn13 = normalize_isbn(raw_isbn)
        if isbn13 is None:
            errors["isbn"] = "No es un ISBN válido: revisa las cifras."

    publish_year = None
    if raw_year := clean(form.get("publish_year")):
        if raw_year.isdigit() and 1000 <= int(raw_year) <= date.today().year + 1:
            publish_year = int(raw_year)
        else:
            errors["publish_year"] = "Escribe el año con cuatro cifras."

    cover_url = clean(form.get("cover_url")) or None
    # Solo http(s): un "javascript:…" en el src de una imagen sería una puerta a XSS.
    if cover_url and (not re.match(r"https?://", cover_url) or len(cover_url) > 300):
        errors["cover_url"] = "Tiene que ser una dirección que empiece por https://."

    # Viene de un campo oculto que rellena la búsqueda por ISBN; se comprueba el formato
    # porque se usa para montar el enlace "Ver en Open Library".
    openlibrary_key = clean(form.get("openlibrary_key")) or None
    if openlibrary_key and not re.fullmatch(r"/(books|works)/OL\d+[MW]", openlibrary_key):
        openlibrary_key = None

    notes = (form.get("notes") or "").strip() or None

    if errors:
        return None, errors
    data = BookInput(
        title, authors, status, isbn13, publish_year, cover_url, openlibrary_key, notes
    )
    return data, {}


def form_values(book: Book) -> dict[str, str]:
    """Lo contrario de `parse_book_form`: el libro como texto para rellenar el formulario."""
    return {
        "title": book.title,
        "authors": "\n".join(a.name for a in book.authors),
        "status": book.status.value,
        "isbn": book.isbn13 or "",
        "publish_year": str(book.publish_year or ""),
        "cover_url": book.cover_url or "",
        "openlibrary_key": book.openlibrary_key or "",
        "notes": book.notes or "",
    }


def find_by_isbn(session: Session, isbn13: str) -> Book | None:
    return session.scalar(select(Book).where(Book.isbn13 == isbn13))


class DuplicateIsbn(Exception):
    def __init__(self, book: Book) -> None:
        self.book = book


def _authors(session: Session, names: list[str]) -> list[Author]:
    """Reutiliza los autores que ya existen, comparando sin tildes ni mayúsculas."""
    existing = {fold(a.name): a for a in session.scalars(select(Author))}
    return [existing.get(fold(n)) or Author(name=n) for n in names]


def _delete_orphan_authors(session: Session) -> None:
    """Borra los autores que se han quedado sin libros, para que no se acumulen."""
    session.flush()
    for author in session.scalars(select(Author).where(~Author.books.any())):
        session.delete(author)


def _apply(session: Session, book: Book, data: BookInput) -> None:
    if data.isbn13:
        other = find_by_isbn(session, data.isbn13)
        if other is not None and other is not book:
            raise DuplicateIsbn(other)
    book.title = data.title
    book.authors = _authors(session, data.authors)
    book.status = data.status
    book.isbn13 = data.isbn13
    book.publish_year = data.publish_year
    book.cover_url = data.cover_url
    book.openlibrary_key = data.openlibrary_key
    book.notes = data.notes


def create_book(session: Session, data: BookInput) -> Book:
    book = Book()
    _apply(session, book, data)
    session.add(book)
    session.commit()
    return book


def update_book(session: Session, book: Book, data: BookInput) -> None:
    _apply(session, book, data)
    _delete_orphan_authors(session)
    session.commit()


def delete_book(session: Session, book: Book) -> None:
    session.delete(book)
    _delete_orphan_authors(session)
    session.commit()
