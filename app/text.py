"""Normalización de texto compartida por el importador, los modelos y la búsqueda."""

import re
import unicodedata


def clean(text: str | None) -> str:
    """Normaliza Unicode (NFC) y colapsa espacios."""
    if text is None:
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(text))).strip()


def fold(text: str | None) -> str:
    """Versión para comparar: sin tildes, en minúsculas."""
    decomposed = unicodedata.normalize("NFD", clean(text).lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
