from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.models import ReadingStatus

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def cover_size(url: str | None, size: str) -> str | None:
    """Cambia el tamaño de una portada de Open Library: S, M o L (…/b/id/123-M.jpg)."""
    if url and url.startswith("https://covers.openlibrary.org/") and url[-6:-5] == "-":
        return f"{url[:-5]}{size}.jpg"
    return url


templates.env.filters["cover_size"] = cover_size
templates.env.globals["STATUSES"] = list(ReadingStatus)
