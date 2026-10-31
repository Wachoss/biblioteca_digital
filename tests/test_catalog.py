from app.models import Author, Book, ReadingStatus
from app.services.catalog import count_by_status, search_books


def titles(books):
    return [b.title for b in books]


def test_search_text_is_computed_on_save(session):
    book = session.query(Book).filter_by(title="Ética para Amador").one()
    assert book.search_text == "etica para amador fernando savater"


def test_search_text_follows_changes(session):
    book = session.query(Book).filter_by(title="Maus").one()
    book.title = "Maus I"
    book.authors.append(Author(name="Françoise Mouly"))
    session.commit()
    assert book.search_text == "maus i art spiegelman francoise mouly"


def test_empty_query_returns_all_sorted_ignoring_accents(session):
    # "Ética" va con la E, no detrás de la "R" como pasaría ordenando por el título tal cual.
    assert titles(search_books(session)) == [
        "100% Cocina",
        "1984",
        "Ética para Amador",
        "Maus",
        "Rebelión en la granja",
    ]


def test_search_ignores_accents_and_case(session):
    assert titles(search_books(session, "ETICA")) == ["Ética para Amador"]
    assert titles(search_books(session, "rebelion")) == ["Rebelión en la granja"]


def test_search_by_author(session):
    assert titles(search_books(session, "orwell")) == ["1984", "Rebelión en la granja"]


def test_all_words_must_match_in_any_order(session):
    assert titles(search_books(session, "orwell 1984")) == ["1984"]
    assert search_books(session, "orwell maus") == []


def test_wildcards_are_literal(session):
    # Sin escapar, "%" casaría con cualquier cosa y "_" con cualquier carácter.
    assert titles(search_books(session, "100%")) == ["100% Cocina"]
    assert search_books(session, "_") == []


def test_filter_by_status(session):
    assert titles(search_books(session, status=ReadingStatus.READ)) == ["1984"]
    assert titles(search_books(session, "orwell", ReadingStatus.PENDING)) == [
        "Rebelión en la granja"
    ]


def test_count_by_status_includes_zeros(session):
    counts = count_by_status(session)
    assert counts[ReadingStatus.PENDING] == 2
    assert counts[ReadingStatus.ABANDONED] == 0
    assert sum(counts.values()) == 5
