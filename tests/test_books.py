"""Añadir, editar y borrar libros. Open Library se sustituye siempre por un falso."""

import httpx
import pytest

from app.isbn import isbn13_to_isbn10, normalize_isbn
from app.main import app
from app.models import Author, Book, ReadingStatus
from app.services.books import parse_book_form
from app.services.openlibrary import (
    OpenLibrary,
    OpenLibraryError,
    get_openlibrary,
    parse_entry,
    parse_year,
)

CIEN_ANOS = "9788437604947"
OL_ENTRY = {
    "key": "/books/OL7574412M",
    "title": "Cien años de soledad",
    "authors": [
        {"url": "https://openlibrary.org/authors/OL4586796A", "name": "Gabriel García Márquez"}
    ],
    "publish_date": "2007",
    "cover": {
        "small": "https://covers.openlibrary.org/b/id/8739161-S.jpg",
        "medium": "https://covers.openlibrary.org/b/id/8739161-M.jpg",
        "large": "https://covers.openlibrary.org/b/id/8739161-L.jpg",
    },
}


# --- ISBN -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("978-84-376-0494-7", CIEN_ANOS),
        (" 978 84 376 0494 7 ", CIEN_ANOS),
        ("84-376-0494-X", CIEN_ANOS),  # ISBN-10 con X final, convertido a 13
        ("843760494x", CIEN_ANOS),
        ("9788437604948", None),  # dígito de control mal
        ("8437604941", None),
        ("1234567890123", None),  # no empieza por 978/979
        ("978843760494", None),  # le falta una cifra
        ("", None),
    ],
)
def test_normalize_isbn(raw, expected):
    assert normalize_isbn(raw) == expected


def test_isbn13_to_isbn10():
    assert isbn13_to_isbn10(CIEN_ANOS) == "843760494X"
    assert isbn13_to_isbn10("9791387522000") is None  # los 979 no tienen ISBN-10


# --- Cliente de Open Library ------------------------------------------------------------


def fake_http(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_lookup_asks_for_both_isbns_and_parses_entry():
    def handler(request):
        assert request.url.params["bibkeys"] == f"ISBN:{CIEN_ANOS},ISBN:843760494X"
        assert request.url.params["jscmd"] == "data"
        # Responde con la clave de 10 cifras, como pasa con libros antiguos.
        return httpx.Response(200, json={"ISBN:843760494X": OL_ENTRY})

    found = OpenLibrary(fake_http(handler)).lookup_isbn(CIEN_ANOS)
    assert found.title == "Cien años de soledad"
    assert found.authors == ["Gabriel García Márquez"]
    assert found.publish_year == 2007
    assert found.cover_url == "https://covers.openlibrary.org/b/id/8739161-M.jpg"
    assert found.openlibrary_key == "/books/OL7574412M"


def test_lookup_unknown_isbn_returns_none():
    client = OpenLibrary(fake_http(lambda r: httpx.Response(200, json={})))
    assert client.lookup_isbn(CIEN_ANOS) is None


@pytest.mark.parametrize(
    "handler",
    [
        lambda r: httpx.Response(503),
        lambda r: httpx.Response(200, text="<html>no es JSON</html>"),
        lambda r: (_ for _ in ()).throw(httpx.ConnectTimeout("tiempo agotado")),
    ],
)
def test_lookup_failures_raise_openlibrary_error(handler):
    with pytest.raises(OpenLibraryError):
        OpenLibrary(fake_http(handler)).lookup_isbn(CIEN_ANOS)


@pytest.mark.parametrize(
    ("text", "year"),
    [("2007", 2007), ("March 2003", 2003), ("1/1/1999", 1999), ("s.f.", None), (None, None)],
)
def test_parse_year(text, year):
    assert parse_year(text) == year


# --- Validación del formulario ---------------------------------------------------------


def test_form_parses_and_cleans():
    data, errors = parse_book_form(
        {
            "title": "  Cien   años de soledad ",
            "authors": "Gabriel García Márquez\n\n gabriel garcia marquez \nOtro Autor",
            "status": "leido",
            "isbn": "84-376-0494-X",
            "publish_year": "2007",
            "notes": "  ",
        }
    )
    assert errors == {}
    assert data.title == "Cien años de soledad"
    assert data.authors == ["Gabriel García Márquez", "Otro Autor"]  # sin repetidos
    assert data.status is ReadingStatus.READ
    assert data.isbn13 == CIEN_ANOS
    assert data.notes is None


def test_form_reports_every_error():
    _, errors = parse_book_form(
        {
            "title": " ",
            "status": "inventado",
            "isbn": "123",
            "publish_year": "dos mil",
            "cover_url": "javascript:alert(1)",
        }
    )
    assert set(errors) == {"title", "status", "isbn", "publish_year", "cover_url"}


def test_form_drops_malformed_openlibrary_key():
    data, _ = parse_book_form({"title": "X", "openlibrary_key": "https://malo.example"})
    assert data.openlibrary_key is None


# --- Páginas ---------------------------------------------------------------------------


class FakeOpenLibrary:
    def __init__(self, result=None, error=False):
        self.result, self.error, self.calls = result, error, []

    def lookup_isbn(self, isbn13):
        self.calls.append(isbn13)
        if self.error:
            raise OpenLibraryError("caída")
        return self.result


@pytest.fixture
def fake_ol():
    """Open Library falsa que devuelve "Cien años de soledad"."""
    fake = FakeOpenLibrary(parse_entry(OL_ENTRY))
    app.dependency_overrides[get_openlibrary] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_openlibrary, None)


def book_by_title(session, title):
    session.expire_all()  # lo que ha guardado la petición, no lo que había en memoria
    return session.query(Book).filter_by(title=title).one_or_none()


def test_new_book_page_without_isbn_shows_empty_form(owner, fake_ol):
    response = owner.get("/libros/nuevo")
    assert response.status_code == 200
    assert "Buscar por ISBN" in response.text
    assert fake_ol.calls == []


def test_isbn_lookup_prefills_form(owner, fake_ol):
    response = owner.get("/libros/nuevo", params={"isbn": "978-84-376-0494-7"})
    assert fake_ol.calls == [CIEN_ANOS]
    assert "Revísalos antes de guardar" in response.text
    assert 'value="Cien años de soledad"' in response.text
    assert "Gabriel García Márquez</textarea>" in response.text
    assert 'value="/books/OL7574412M"' in response.text


def test_isbn_lookup_does_not_save_anything(owner, fake_ol, session):
    owner.get("/libros/nuevo", params={"isbn": CIEN_ANOS})
    assert book_by_title(session, "Cien años de soledad") is None


def test_invalid_isbn_is_not_sent_to_openlibrary(owner, fake_ol):
    response = owner.get("/libros/nuevo", params={"isbn": "9788437604948"})
    assert response.status_code == 422
    assert "No es un ISBN válido" in response.text
    assert fake_ol.calls == []


def test_isbn_not_in_openlibrary_offers_manual_form(owner, fake_ol):
    fake_ol.result = None
    response = owner.get("/libros/nuevo", params={"isbn": CIEN_ANOS})
    assert "Open Library no tiene este ISBN" in response.text
    assert f'name="isbn" value="{CIEN_ANOS}"' in response.text


def test_openlibrary_down_offers_manual_form(owner, fake_ol):
    fake_ol.error = True
    response = owner.get("/libros/nuevo", params={"isbn": CIEN_ANOS})
    assert response.status_code == 200
    assert "No se ha podido consultar Open Library" in response.text


def test_lookup_of_isbn_already_owned_links_to_it(owner, fake_ol, session):
    book = session.query(Book).filter_by(title="Maus").one()
    book.isbn13 = CIEN_ANOS
    session.commit()
    response = owner.get("/libros/nuevo", params={"isbn": CIEN_ANOS})
    assert "Ya tienes este libro" in response.text
    assert f"/libros/{book.id}" in response.text
    assert fake_ol.calls == []


def test_create_book(owner, session):
    form = {
        "title": "Cien años de soledad",
        "authors": "Gabriel García Márquez",
        "status": "leyendo",
        "isbn": CIEN_ANOS,
        "publish_year": "2007",
        "cover_url": "https://covers.openlibrary.org/b/id/8739161-M.jpg",
        "openlibrary_key": "/books/OL7574412M",
    }
    response = owner.post("/libros/nuevo", data=form, follow_redirects=False)
    assert response.status_code == 303
    book = book_by_title(session, "Cien años de soledad")
    assert response.headers["location"].endswith(f"/libros/{book.id}")
    assert [a.name for a in book.authors] == ["Gabriel García Márquez"]
    assert book.status is ReadingStatus.READING
    assert book.search_text == "cien anos de soledad gabriel garcia marquez"
    # Y aparece en el catálogo y en la búsqueda sin tildes.
    assert "Cien años de soledad" in owner.get("/", params={"q": "garcia"}).text


def test_create_book_reuses_existing_author(owner, session):
    owner.post("/libros/nuevo", data={"title": "Homenaje a Cataluña", "authors": "george orwell"})
    assert session.query(Author).filter(Author.name.ilike("%orwell%")).count() == 1


def test_create_book_with_errors_keeps_what_was_typed(owner, session):
    response = owner.post("/libros/nuevo", data={"title": "", "notes": "mis notas", "isbn": "1"})
    assert response.status_code == 422
    assert "El título es obligatorio" in response.text
    assert "mis notas</textarea>" in response.text
    assert session.query(Book).count() == 5


def test_create_book_with_duplicate_isbn_is_refused(owner, session):
    owner.post("/libros/nuevo", data={"title": "Uno", "isbn": CIEN_ANOS})
    response = owner.post("/libros/nuevo", data={"title": "Otro", "isbn": "84-376-0494-X"})
    assert response.status_code == 409
    assert "Ya tienes un libro con este ISBN" in response.text
    assert book_by_title(session, "Otro") is None


def test_edit_page_is_prefilled(owner, session):
    book = session.query(Book).filter_by(title="1984").one()
    response = owner.get(f"/libros/{book.id}/editar")
    assert 'value="1984"' in response.text
    assert "George Orwell</textarea>" in response.text
    assert '<option value="leido" selected>' in response.text


def test_edit_book(owner, session):
    book = session.query(Book).filter_by(title="Maus").one()
    form = {"title": "Maus: relato de un superviviente", "authors": "Art Spiegelman"}
    form |= {"status": "abandonado", "notes": "Dejado a Thamires"}
    response = owner.post(f"/libros/{book.id}/editar", data=form, follow_redirects=False)
    assert response.status_code == 303
    session.expire_all()
    assert book.title == "Maus: relato de un superviviente"
    assert book.status is ReadingStatus.ABANDONED
    assert book.notes == "Dejado a Thamires"


def test_edit_removes_authors_left_without_books(owner, session):
    book = session.query(Book).filter_by(title="Maus").one()
    owner.post(f"/libros/{book.id}/editar", data={"title": "Maus", "authors": "Otro Nombre"})
    session.expire_all()
    assert session.query(Author).filter_by(name="Art Spiegelman").one_or_none() is None


def test_edit_cannot_steal_isbn_from_another_book(owner, session):
    maus, cocina = (session.query(Book).filter_by(title=t).one() for t in ("Maus", "100% Cocina"))
    maus.isbn13 = CIEN_ANOS
    session.commit()
    response = owner.post(
        f"/libros/{cocina.id}/editar", data={"title": "100% Cocina", "isbn": CIEN_ANOS}
    )
    assert response.status_code == 409
    session.expire_all()
    assert cocina.isbn13 is None


def test_edit_keeping_its_own_isbn_is_fine(owner, session):
    book = session.query(Book).filter_by(title="Maus").one()
    book.isbn13 = CIEN_ANOS
    session.commit()
    data = {"title": "Maus", "isbn": CIEN_ANOS}
    assert (
        owner.post(f"/libros/{book.id}/editar", data=data, follow_redirects=False).status_code
        == 303
    )


def test_delete_book(owner, session):
    book = session.query(Book).filter_by(title="Maus").one()
    response = owner.post(f"/libros/{book.id}/borrar", follow_redirects=False)
    assert response.status_code == 303
    assert owner.get(f"/libros/{book.id}").status_code == 404
    session.expire_all()
    assert session.query(Author).filter_by(name="Art Spiegelman").one_or_none() is None
    # Orwell sigue: tiene otro libro.
    orwell_book = session.query(Book).filter_by(title="1984").one()
    owner.post(f"/libros/{orwell_book.id}/borrar")
    assert session.query(Author).filter_by(name="George Orwell").count() == 1


def test_edit_or_delete_missing_book_is_404(owner):
    assert owner.get("/libros/999/editar").status_code == 404
    assert owner.post("/libros/999/borrar").status_code == 404
