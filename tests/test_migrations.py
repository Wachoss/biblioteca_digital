from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from app.models import Base

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def alembic_config(url: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", url)
    return config


def test_migrations_match_models(tmp_path):
    """Si cambias models.py y olvidas crear la migración, este test falla."""
    url = f"sqlite:///{tmp_path / 'test.db'}"
    command.upgrade(alembic_config(url), "head")
    with create_engine(url).connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_downgrade_and_upgrade_again(tmp_path):
    config = alembic_config(f"sqlite:///{tmp_path / 'test.db'}")
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")


def test_search_text_backfill(tmp_path):
    """La migración rellena search_text de los libros que ya estaban en la base de datos."""
    url = f"sqlite:///{tmp_path / 'test.db'}"
    config = alembic_config(url)
    command.upgrade(config, "1668674c7fed")  # esquema anterior a search_text
    with create_engine(url).begin() as conn:
        conn.exec_driver_sql("INSERT INTO books (id, title, status) VALUES (1, 'Ética', 'leido')")
        conn.exec_driver_sql("INSERT INTO authors (id, name) VALUES (1, 'Fernando Savater')")
        conn.exec_driver_sql("INSERT INTO book_authors VALUES (1, 1)")
    command.upgrade(config, "head")
    with create_engine(url).connect() as conn:
        text = conn.exec_driver_sql("SELECT search_text FROM books").scalar_one()
    assert text == "etica fernando savater"
