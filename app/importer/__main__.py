"""Uso:

python -m app.importer prepare "Biblioteca Digital.xlsx"   # fases 1 y 2 -> review.csv
python -m app.importer load review.csv                      # fase 4 -> biblioteca.db
"""

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import make_engine
from app.importer.enrich import OpenLibraryClient, enrich
from app.importer.load import load
from app.importer.normalize import read_excel
from app.importer.review import read_review, write_review

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def prepare(excel: Path, out: Path, cache: Path) -> None:
    books = read_excel(excel)
    client = OpenLibraryClient(cache)
    rows = []
    for i, book in enumerate(books, 1):
        cand = enrich(book, client)
        print(f"[{i}/{len(books)}] {book.title[:50]:50} {cand.score if cand else '-'}")
        rows.append((book, cand))
    write_review(rows, out)
    print(f"Escrito {out}. Revisa las filas con ACEPTAR=no y luego ejecuta 'load'.")


def migrate(url: str) -> None:
    """Deja la base de datos en la última migración (equivale a `alembic upgrade head`)."""
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")


def run_load(review: Path, url: str) -> None:
    migrate(url)
    engine = make_engine(url)
    with Session(engine) as session, session.begin():  # commit al salir, rollback si falla
        created, updated = load(session, read_review(review))
    print(f"Libros creados: {created}, actualizados: {updated}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.importer")
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser(
        "prepare", help="Lee el Excel, busca en Open Library y escribe el CSV de revisión"
    )
    prep.add_argument("excel", type=Path)
    prep.add_argument("--out", type=Path, default=Path("review.csv"))
    prep.add_argument("--cache", type=Path, default=Path(".openlibrary_cache.json"))
    load_cmd = sub.add_parser("load", help="Carga el CSV revisado en la base de datos")
    load_cmd.add_argument("review", type=Path)
    load_cmd.add_argument("--db", default=get_settings().database_url)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.excel, args.out, args.cache)
    else:
        run_load(args.review, args.db)


if __name__ == "__main__":
    main()
