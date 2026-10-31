import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import get_session
from app.main import app
from app.models import Author, Base, Book, ReadingStatus


@pytest.fixture
def engine():
    # Base de datos en memoria compartida por todas las conexiones del test.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        orwell = Author(name="George Orwell")
        session.add_all(
            [
                Book(title="1984", authors=[orwell], status=ReadingStatus.READ),
                Book(title="Rebelión en la granja", authors=[orwell]),
                Book(title="Maus", authors=[Author(name="Art Spiegelman")]),
                Book(
                    title="Ética para Amador",
                    authors=[Author(name="Fernando Savater")],
                    status=ReadingStatus.READING,
                    cover_url="https://covers.openlibrary.org/b/id/123-M.jpg",
                ),
                Book(title="100% Cocina", status=ReadingStatus.REFERENCE),
            ]
        )
        session.commit()
        yield session


@pytest.fixture
def client(engine, session):
    def override():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()
