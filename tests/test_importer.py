import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.importer.enrich import OpenLibraryClient, enrich, pick_isbn13, score
from app.importer.load import load
from app.importer.normalize import RawBook, parse_authors, parse_row, parse_status
from app.importer.review import merge_authors, read_review, write_review
from app.models import Author, Base, Book, ReadingStatus


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Leido", ReadingStatus.READ),
        ("Leído", ReadingStatus.READ),
        ("Leido ", ReadingStatus.READ),
        ("No leído", ReadingStatus.PENDING),
        ("No terminado", ReadingStatus.ABANDONED),
        ("Para consultar", ReadingStatus.REFERENCE),
        ("consulta", ReadingStatus.REFERENCE),
    ],
)
def test_parse_status(raw, expected):
    assert parse_status(raw) is expected


def test_parse_status_rejects_unknown():
    with pytest.raises(ValueError):
        parse_status("Prestado")


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, []),
        ("Diversos Autores", []),
        ("Blon / Pablo Perez", ["Blon", "Pablo Perez"]),
        ("Takeshi Hirano/Mitsuru Nagata", ["Takeshi Hirano", "Mitsuru Nagata"]),
        ("Gabriel garcía Márquez", ["Gabriel García Márquez"]),
        ("Fernando De Rojas", ["Fernando De Rojas"]),
        ("Salvador Montaña ", ["Salvador Montaña"]),
        ("GREGORY BASSHAM", ["Gregory Bassham"]),
        ("CJ Cannon", ["CJ Cannon"]),
    ],
)
def test_parse_authors(raw, expected):
    assert parse_authors(raw) == expected


def test_parse_row():
    book = parse_row(
        (
            26.0,
            "El libro de la Filosofía ",
            "Gregory Bassham",
            "Para consultar",
            "Dejado a Thamires",
        )
    )
    assert book == RawBook(
        "excel:26",
        "El libro de la Filosofía",
        ["Gregory Bassham"],
        ReadingStatus.REFERENCE,
        "Dejado a Thamires",
    )


def fake_client(tmp_path, docs_by_title):
    calls = []

    def handler(request):
        calls.append(dict(request.url.params))
        docs = docs_by_title.get(request.url.params["title"], [])
        if "author" in request.url.params and request.url.params["author"] == "Aldoux Husley":
            docs = []  # Open Library no encuentra el autor mal escrito
        return httpx.Response(200, json={"docs": docs})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenLibraryClient(tmp_path / "cache.json", http=http, delay=0), calls


BRAVE = {
    "key": "/works/OL64468W",
    "title": "Un mundo feliz",
    "author_name": ["Aldous Huxley"],
    "isbn": ["8497594258", "9788497594257"],
    "cover_i": 123,
    "first_publish_year": 1932,
}


def test_enrich_retries_without_author_and_caches(tmp_path):
    client, calls = fake_client(tmp_path, {"Un mundo feliz": [BRAVE]})
    book = RawBook("excel:85", "Un mundo feliz", ["Aldoux Husley"], ReadingStatus.READ)

    cand = enrich(book, client)
    assert cand.isbn13 == "9788497594257"
    assert cand.cover_url == "https://covers.openlibrary.org/b/id/123-M.jpg"
    assert cand.score >= 85
    assert len(calls) == 2  # con autor (nada) y solo por título

    enrich(book, client)
    assert len(calls) == 2  # la segunda vez sale de la caché


def test_review_roundtrip_and_idempotent_load(tmp_path):
    client, _ = fake_client(tmp_path, {"Un mundo feliz": [BRAVE]})
    brave = RawBook("excel:85", "Un mundo feliz", ["Aldoux Husley"], ReadingStatus.READ)
    mito = RawBook("excel:18", "Mitopedia", [], ReadingStatus.REFERENCE)
    path = tmp_path / "review.csv"
    write_review([(brave, enrich(brave, client)), (mito, enrich(mito, client))], path)

    reviewed = {b.import_ref: b for b in read_review(path)}
    assert reviewed["excel:85"].authors == ["Aldous Huxley"]  # corregido por Open Library
    assert reviewed["excel:85"].isbn13 == "9788497594257"
    assert reviewed["excel:18"].isbn13 is None

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    for expected in [(2, 0), (0, 2)]:  # la segunda carga actualiza, no duplica
        with Session(engine) as session, session.begin():
            assert load(session, list(reviewed.values())) == expected
    with Session(engine) as session:
        assert session.scalar(select(func.count(Book.id))) == 2
        assert session.scalar(select(func.count(Author.id))) == 1


def test_pick_isbn13_only_spanish_editions():
    assert pick_isbn13(["7544277617", "9787544277617", "9788497592437"]) == "9788497592437"
    assert pick_isbn13(["9783492280648", "0307887436"]) is None


def test_score_penalises_extra_words():
    book = RawBook("excel:32", "1984", [], ReadingStatus.READ)
    assert score(book, "1984 (adaptation)", []) < 85
    assert score(book, "1984", []) == 100


@pytest.mark.parametrize(
    "excel, openlibrary, expected",
    [
        (["Ernest Clime"], ["Ernest Cline"], ["Ernest Cline"]),
        # Traductores e ilustradores no se añaden
        (["Lord Byron"], ["Lord Byron", "José C. Vales"], ["Lord Byron"]),
        # Nombres en otro alfabeto no sustituyen al del Excel
        (["Kentaro Yabuki"], ["矢吹健太朗"], ["Kentaro Yabuki"]),
        ([], ["CURATORIS Y TOMIC DRACONIS"], ["Curatoris y Tomic Draconis"]),
    ],
)
def test_merge_authors(excel, openlibrary, expected):
    assert merge_authors(excel, openlibrary) == expected
