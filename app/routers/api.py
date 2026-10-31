"""API JSON de solo lectura. Las mismas consultas que las páginas, otro formato."""

from fastapi import APIRouter, HTTPException

from app.db import SessionDep
from app.models import ReadingStatus
from app.schemas import BookOut
from app.services import catalog

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/books")
def list_books(
    session: SessionDep, q: str = "", status: ReadingStatus | None = None
) -> list[BookOut]:
    # Aquí un estado inválido da 422: quien usa la API debe saber que se ha equivocado.
    return catalog.search_books(session, q, status)


@router.get("/books/{book_id}")
def get_book(session: SessionDep, book_id: int) -> BookOut:
    book = catalog.get_book(session, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    return book
