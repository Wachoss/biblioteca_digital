"""Punto de entrada: `uv run fastapi dev app/main.py`."""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Book

BASE_DIR = Path(__file__).parent

app = FastAPI(title="Biblioteca Digital")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

SessionDep = Annotated[Session, Depends(get_session)]


@app.get("/", response_class=HTMLResponse)
def home(request: Request, session: SessionDep):
    total = session.scalar(select(func.count()).select_from(Book))
    return templates.TemplateResponse(request, "index.html", {"total": total})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
