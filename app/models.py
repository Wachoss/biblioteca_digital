"""Modelos de datos de la biblioteca (SQLAlchemy 2.x, estilo tipado)."""

import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Table, Text, event, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from app.text import fold


class Base(DeclarativeBase):
    pass


class ReadingStatus(enum.StrEnum):
    PENDING = "pendiente"
    READING = "leyendo"
    READ = "leido"
    ABANDONED = "abandonado"
    # Libros que no se leen de corrido: diccionarios, poesía, guías...
    REFERENCE = "consulta"

    @property
    def label(self) -> str:
        """Texto para mostrar en la interfaz (el valor guardado no lleva tildes)."""
        return _STATUS_LABELS[self]


_STATUS_LABELS = {
    ReadingStatus.PENDING: "Pendiente",
    ReadingStatus.READING: "Leyendo",
    ReadingStatus.READ: "Leído",
    ReadingStatus.ABANDONED: "Abandonado",
    ReadingStatus.REFERENCE: "De consulta",
}


# Tabla intermedia de la relación muchos a muchos libro <-> autor.
book_authors = Table(
    "book_authors",
    Base.metadata,
    Column("book_id", ForeignKey("books.id", ondelete="CASCADE"), primary_key=True),
    Column("author_id", ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True),
)


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)

    books: Mapped[list["Book"]] = relationship(secondary=book_authors, back_populates="authors")


class Book(Base):
    __tablename__ = "books"

    # Clave sustituta: el ISBN no sirve como clave porque muchos libros no lo tienen.
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    status: Mapped[ReadingStatus] = mapped_column(
        Enum(ReadingStatus, values_callable=lambda e: [m.value for m in e]),
        default=ReadingStatus.PENDING,
    )
    # Único pero opcional: SQLite (y PostgreSQL) permiten varios NULL en una columna UNIQUE.
    isbn13: Mapped[str | None] = mapped_column(String(13), unique=True)
    openlibrary_key: Mapped[str | None] = mapped_column(String(50))
    cover_url: Mapped[str | None] = mapped_column(String(300))
    publish_year: Mapped[int | None]
    notes: Mapped[str | None] = mapped_column(Text)
    # Origen del registro (p. ej. "excel:26"); permite reimportar sin duplicar.
    import_ref: Mapped[str | None] = mapped_column(String(50), unique=True)
    # Título y autores sin tildes ni mayúsculas, para buscar con LIKE (ver app/services/catalog.py).
    # Es un dato derivado: no se escribe a mano, lo recalcula `_update_search_text` al guardar.
    search_text: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    authors: Mapped[list[Author]] = relationship(
        secondary=book_authors, back_populates="books", lazy="selectin"
    )


def build_search_text(title: str, author_names: list[str]) -> str:
    return fold(" ".join([title, *author_names]))


@event.listens_for(Session, "before_flush")
def _update_search_text(session: Session, _flush_context, _instances) -> None:
    """Recalcula `search_text` de cada libro nuevo o modificado justo antes de guardarlo.

    Así no depende de que quien escriba (importador, formularios del hito 4, tests) se
    acuerde de hacerlo. Limitación: renombrar un autor no marca sus libros como
    modificados; si algún día se edita un autor, hay que tocar también sus libros.
    """
    for obj in (*session.new, *session.dirty):
        if isinstance(obj, Book):
            obj.search_text = build_search_text(obj.title, [a.name for a in obj.authors])
