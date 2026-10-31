"""Consultas del catálogo. Las usan igual las páginas HTML, la API JSON y los tests."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Book, ReadingStatus
from app.text import fold


def search_books(
    session: Session, query: str = "", status: ReadingStatus | None = None
) -> list[Book]:
    """Libros cuyo título o autores contienen todas las palabras de `query`.

    La búsqueda no distingue tildes ni mayúsculas porque se compara la versión "plegada"
    de la consulta con la columna `search_text`, que ya está plegada. Cada palabra puede
    aparecer en cualquier orden y sitio: "orwell 1984" encuentra "1984" de George Orwell.
    """
    stmt = select(Book)
    for word in fold(query).split():
        # autoescape: un "%" o "_" escrito por el usuario se busca literal, no como comodín.
        stmt = stmt.where(Book.search_text.contains(word, autoescape=True))
    if status is not None:
        stmt = stmt.where(Book.status == status)
    # search_text empieza por el título plegado, así que ordena por título sin que las
    # tildes manden "Ética" detrás de la "Z" (lo que pasaría ordenando por `title`).
    stmt = stmt.order_by(Book.search_text)
    return list(session.scalars(stmt))


def count_by_status(session: Session) -> dict[ReadingStatus, int]:
    """Número de libros en cada estado, incluidos los que tienen cero."""
    rows = session.execute(select(Book.status, func.count()).group_by(Book.status))
    counts = dict.fromkeys(ReadingStatus, 0)
    counts.update({status: n for status, n in rows})
    return counts


def get_book(session: Session, book_id: int) -> Book | None:
    return session.get(Book, book_id)
