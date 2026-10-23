"""Fase 2: buscar cada libro en Open Library y puntuar el mejor candidato."""

import json
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from rapidfuzz import fuzz

from app.importer.normalize import RawBook, fold

SEARCH_URL = "https://openlibrary.org/search.json"
COVER_URL = "https://covers.openlibrary.org/b/id/{}-M.jpg"
FIELDS = "key,title,author_name,isbn,cover_i,first_publish_year"
# Open Library pide identificarse con un User-Agent con contacto.
USER_AGENT = "BibliotecaDigital-importer/0.1 (proyecto personal)"

AUTO_ACCEPT_SCORE = 85


@dataclass
class Candidate:
    title: str
    authors: list[str]
    isbn13: str | None
    openlibrary_key: str
    cover_url: str | None
    publish_year: int | None
    score: float


# Prefijos de ISBN de España (incluye catalán y valenciano): 978-84 y 979-13.
LOCAL_ISBN_PREFIXES = ("97884", "97913")


def pick_isbn13(isbns: list[str]) -> str | None:
    """Elige un ISBN-13 de una edición española, o ninguno.

    `isbn` mezcla los ISBN de todas las ediciones de la obra (chinas, alemanas...).
    Un ISBN de otra edición es peor que no tener ISBN: lo dejamos vacío y se
    añade después, por ejemplo con el escáner.
    """
    return next(
        (i for i in isbns if len(i) == 13 and i.isdigit() and i.startswith(LOCAL_ISBN_PREFIXES)),
        None,
    )


def score(book: RawBook, title: str, authors: list[str]) -> float:
    """Similitud 0-100.

    token_set_ratio da 100 si un título contiene al otro ("1984" y "1984 (adaptation)"),
    y token_sort_ratio penaliza las palabras de más; la media equilibra las dos.
    """
    a, b = fold(book.title), fold(title)
    title_score = (fuzz.token_set_ratio(a, b) + fuzz.token_sort_ratio(a, b)) / 2
    if not book.authors:
        return round(title_score, 1)
    author_score = max(
        (fuzz.token_set_ratio(fold(a), fold(b)) for a in book.authors for b in authors),
        default=0,
    )
    # El título pesa más: un autor mal escrito ("Aldoux Husley") no debe hundir la nota.
    return round(0.7 * title_score + 0.3 * author_score, 1)


def best_candidate(book: RawBook, docs: list[dict]) -> Candidate | None:
    candidates = [
        Candidate(
            title=doc.get("title", ""),
            authors=doc.get("author_name", []),
            isbn13=pick_isbn13(doc.get("isbn", [])),
            openlibrary_key=doc["key"],
            cover_url=COVER_URL.format(doc["cover_i"]) if doc.get("cover_i") else None,
            publish_year=doc.get("first_publish_year"),
            score=score(book, doc.get("title", ""), doc.get("author_name", [])),
        )
        for doc in docs
    ]
    return max(candidates, key=lambda c: c.score, default=None)


class OpenLibraryClient:
    """Cliente con caché en disco y límite de una petición por segundo."""

    def __init__(self, cache_path: Path, http: httpx.Client | None = None, delay: float = 1.0):
        self.cache_path = cache_path
        self.cache: dict[str, list[dict]] = (
            json.loads(cache_path.read_text()) if cache_path.exists() else {}
        )
        self.http = http or httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=20)
        self.delay = delay
        self._last_request = 0.0

    def search(self, title: str, author: str | None) -> list[dict]:
        params = {"title": title, "fields": FIELDS, "limit": 5}
        if author:
            params["author"] = author
        key = json.dumps(params, sort_keys=True, ensure_ascii=False)
        if key not in self.cache:
            wait = self._last_request + self.delay - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            response = self.http.get(SEARCH_URL, params=params)
            self._last_request = time.monotonic()
            response.raise_for_status()
            self.cache[key] = response.json().get("docs", [])
            self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1))
        return self.cache[key]


def enrich(book: RawBook, client: OpenLibraryClient) -> Candidate | None:
    author = book.authors[0] if book.authors else None
    docs = client.search(book.title, author)
    if not docs and author:
        # Reintento solo por título: rescata autores mal escritos.
        docs = client.search(book.title, None)
    return best_candidate(book, docs)
