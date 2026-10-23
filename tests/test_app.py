import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import get_session
from app.main import app
from app.models import Base, Book


@pytest.fixture
def client():
    # Base de datos en memoria compartida por todas las conexiones del test.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([Book(title="Maus"), Book(title="1984")])
        session.commit()

    def override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_home_counts_books(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "2 libros" in response.text


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}
