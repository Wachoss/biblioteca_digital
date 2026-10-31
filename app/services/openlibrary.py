"""Buscar un libro en Open Library por su ISBN, para rellenar el formulario de alta.

Se usa el endpoint `/api/books?jscmd=data` porque devuelve en una sola petición todo lo
que hace falta: título, nombres de los autores, portada y fecha. La alternativa,
`/isbn/{isbn}.json`, devuelve la edición con los autores como claves (`/authors/OL…A`)
y habría que hacer una petición más por autor.

No se reutiliza el cliente del importador (`app/importer/enrich.py`): aquel busca por
título y autor, puntúa candidatos y guarda una caché en disco para cientos de consultas
seguidas. Aquí hay una sola consulta exacta por ISBN, y lo importante es otra cosa:
responder rápido y no romper la página si Open Library falla.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

import httpx

from app.isbn import isbn13_to_isbn10
from app.text import clean

BOOKS_URL = "https://openlibrary.org/api/books"
# Open Library pide identificarse con un User-Agent.
USER_AGENT = (
    "BibliotecaDigital/0.1 (proyecto personal; https://github.com/Wachoss/biblioteca_digital)"
)


@dataclass
class BookData:
    title: str
    authors: list[str]
    publish_year: int | None
    cover_url: str | None
    openlibrary_key: str | None


class OpenLibraryError(Exception):
    """Open Library no ha respondido (red caída, tiempo agotado, error 5xx...)."""


def parse_year(publish_date: str | None) -> int | None:
    """Open Library guarda la fecha como texto libre: "2003", "March 2003", "1/1/2003"..."""
    match = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", publish_date or "")
    return int(match.group(1)) if match else None


def parse_entry(entry: dict) -> BookData:
    cover = entry.get("cover") or {}
    return BookData(
        title=clean(entry.get("title")),
        authors=[clean(a["name"]) for a in entry.get("authors", []) if a.get("name")],
        publish_year=parse_year(entry.get("publish_date")),
        # Se guarda la mediana (-M); la plantilla la cambia a -L en la ficha.
        cover_url=cover.get("medium"),
        openlibrary_key=entry.get("key"),
    )


class OpenLibrary:
    def __init__(self, http: httpx.Client | None = None) -> None:
        # 8 segundos: alguien está esperando delante de la pantalla.
        self.http = http or httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=8)

    def lookup_isbn(self, isbn13: str) -> BookData | None:
        """Datos del libro, o None si Open Library no conoce ese ISBN."""
        # Se pregunta por el ISBN-13 y por el ISBN-10 a la vez: muchos libros antiguos
        # solo están registrados con el de 10 cifras.
        keys = [f"ISBN:{isbn13}"]
        if isbn10 := isbn13_to_isbn10(isbn13):
            keys.append(f"ISBN:{isbn10}")
        params = {"bibkeys": ",".join(keys), "jscmd": "data", "format": "json"}
        try:
            response = self.http.get(BOOKS_URL, params=params)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OpenLibraryError(str(exc)) from exc
        entry = next((data[k] for k in keys if data.get(k)), None)
        return parse_entry(entry) if entry else None


@lru_cache
def get_openlibrary() -> OpenLibrary:
    """Dependencia de FastAPI: un único cliente, que reutiliza las conexiones.

    Los tests la sustituyen por uno falso con `app.dependency_overrides`, así que nunca
    llaman a la Open Library de verdad.
    """
    return OpenLibrary()
