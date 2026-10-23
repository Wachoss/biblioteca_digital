"""Modelos de datos de la biblioteca (SQLAlchemy 2.x, estilo tipado)."""

import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Table, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ReadingStatus(enum.StrEnum):
    PENDING = "pendiente"
    READING = "leyendo"
    READ = "leido"
    ABANDONED = "abandonado"
    # Libros que no se leen de corrido: diccionarios, poesía, guías...
    REFERENCE = "consulta"


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
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    authors: Mapped[list[Author]] = relationship(
        secondary=book_authors, back_populates="books", lazy="selectin"
    )
