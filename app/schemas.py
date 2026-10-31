"""Esquemas de Pydantic para la API JSON: qué campos de cada modelo se exponen."""

from pydantic import BaseModel, ConfigDict, field_validator

from app.models import Author, ReadingStatus


class BookOut(BaseModel):
    # from_attributes permite construirlo directamente desde un objeto Book de SQLAlchemy.
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    authors: list[str]
    status: ReadingStatus
    isbn13: str | None
    publish_year: int | None
    cover_url: str | None
    openlibrary_key: str | None
    notes: str | None

    @field_validator("authors", mode="before")
    @classmethod
    def author_names(cls, value: list[Author | str]) -> list[str]:
        # En la API un autor es solo su nombre; el id interno no le sirve a nadie.
        return [a.name if isinstance(a, Author) else a for a in value]
