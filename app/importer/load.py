"""Fase 4: cargar el CSV revisado en la base de datos, de forma idempotente."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.importer.normalize import fold
from app.importer.review import ReviewedBook
from app.models import Author, Book


def get_or_create_author(session: Session, name: str, cache: dict[str, Author]) -> Author:
    # Se compara sin tildes ni mayúsculas para no crear "Angel Martín" y "Ángel Martín".
    key = fold(name)
    if key not in cache:
        cache[key] = Author(name=name)
        session.add(cache[key])
    return cache[key]


def load(session: Session, books: list[ReviewedBook]) -> tuple[int, int]:
    """Inserta o actualiza cada libro por su import_ref. Devuelve (creados, actualizados).

    No hace commit: quien llama decide la transacción (todo o nada).
    """
    authors = {fold(a.name): a for a in session.scalars(select(Author))}
    existing = {
        b.import_ref: b for b in session.scalars(select(Book).where(Book.import_ref.is_not(None)))
    }
    created = updated = 0
    for item in books:
        book = existing.get(item.import_ref)
        if book is None:
            book = Book(import_ref=item.import_ref)
            session.add(book)
            created += 1
        else:
            updated += 1
        book.title = item.title
        book.status = item.status
        book.notes = item.notes
        book.isbn13 = item.isbn13
        book.openlibrary_key = item.openlibrary_key
        book.cover_url = item.cover_url
        book.publish_year = item.publish_year
        book.authors = [get_or_create_author(session, n, authors) for n in item.authors]
    return created, updated
