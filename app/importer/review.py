"""Fase 3: el CSV de revisión que se edita a mano (LibreOffice, Excel...).

Las columnas en MAYÚSCULAS son las que se cargan; el resto son referencia para decidir.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz

from app.importer.enrich import AUTO_ACCEPT_SCORE, Candidate
from app.importer.normalize import RawBook, fix_name_case, parse_authors, parse_status
from app.models import ReadingStatus
from app.text import clean, fold

AUTHOR_SEP = " / "
LOADED = [
    "import_ref",
    "ACEPTAR",
    "TITULO",
    "AUTORES",
    "ESTADO",
    "ISBN13",
    "OPENLIBRARY_KEY",
    "COVER_URL",
    "ANYO",
    "NOTAS",
]
REFERENCE = ["puntuacion", "excel_titulo", "excel_autores", "ol_titulo", "ol_autores"]


@dataclass
class ReviewedBook:
    import_ref: str
    title: str
    authors: list[str]
    status: ReadingStatus
    notes: str | None
    isbn13: str | None = None
    openlibrary_key: str | None = None
    cover_url: str | None = None
    publish_year: int | None = None


def merge_authors(excel: list[str], openlibrary: list[str]) -> list[str]:
    """Corrige la grafía de los autores del Excel con la de Open Library.

    Open Library no distingue autor, traductor e ilustrador, así que no se
    añaden nombres nuevos: solo se rellena si el Excel no tenía autor.
    """
    openlibrary = [fix_name_case(a) for a in openlibrary]
    if not excel:
        return openlibrary
    merged = []
    for name in excel:
        best = max(
            openlibrary, key=lambda o: fuzz.token_set_ratio(fold(name), fold(o)), default=None
        )
        good = best is not None and fuzz.token_set_ratio(fold(name), fold(best)) >= 80
        merged.append(best if good else name)
    # "Blon / Pablo Perez" son la misma persona: ambos casan con "Pablo Pérez Rueda (Blon)".
    return list(dict.fromkeys(merged))


def to_row(book: RawBook, cand: Candidate | None) -> dict:
    accept = cand is not None and cand.score >= AUTO_ACCEPT_SCORE
    # El título se queda el del Excel: Open Library suele devolver el original
    # ("Nineteen Eighty-Four"), no el de tu edición.
    authors = merge_authors(book.authors, cand.authors) if accept else book.authors
    return {
        "import_ref": book.import_ref,
        "ACEPTAR": "si" if accept else "no",
        "TITULO": book.title,
        "AUTORES": AUTHOR_SEP.join(authors),
        "ESTADO": book.status.value,
        "ISBN13": cand.isbn13 if cand else "",
        "OPENLIBRARY_KEY": cand.openlibrary_key if cand else "",
        "COVER_URL": (cand.cover_url or "") if cand else "",
        "ANYO": (cand.publish_year or "") if cand else "",
        "NOTAS": book.notes or "",
        "puntuacion": cand.score if cand else 0,
        "excel_titulo": book.title,
        "excel_autores": AUTHOR_SEP.join(book.authors),
        "ol_titulo": cand.title if cand else "",
        "ol_autores": AUTHOR_SEP.join(cand.authors) if cand else "",
    }


def write_review(rows: list[tuple[RawBook, Candidate | None]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOADED + REFERENCE)
        writer.writeheader()
        # Primero las dudosas, que son las que hay que mirar.
        for row in sorted((to_row(b, c) for b, c in rows), key=lambda r: r["puntuacion"]):
            writer.writerow(row)


def from_row(row: dict) -> ReviewedBook:
    accept = clean(row["ACEPTAR"]).lower() in {"si", "sí", "s", "yes", "1"}

    def ol(column: str) -> str | None:
        return (clean(row[column]) or None) if accept else None

    year = ol("ANYO")
    return ReviewedBook(
        import_ref=row["import_ref"],
        title=clean(row["TITULO"]),
        authors=parse_authors(row["AUTORES"]),
        status=parse_status(row["ESTADO"]),
        notes=clean(row["NOTAS"]) or None,
        isbn13=ol("ISBN13"),
        openlibrary_key=ol("OPENLIBRARY_KEY"),
        cover_url=ol("COVER_URL"),
        publish_year=int(float(year)) if year else None,
    )


def read_review(path: Path) -> list[ReviewedBook]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return [from_row(row) for row in csv.DictReader(f)]
