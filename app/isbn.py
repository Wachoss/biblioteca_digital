"""Validar y normalizar ISBN.

Un ISBN lleva un dígito de control al final: sirve para detectar casi cualquier error
al teclearlo (una cifra mal o dos cifras cambiadas de sitio). Por eso se comprueba
antes de preguntar a Open Library, en vez de gastar una petición en un número imposible.
"""

import re


def _isbn10_ok(digits: str) -> bool:
    # Pesos 10, 9, ..., 1; la suma debe ser múltiplo de 11. La "X" final vale 10.
    values = [10 if c == "X" else int(c) for c in digits]
    return sum(w * v for w, v in zip(range(10, 0, -1), values, strict=True)) % 11 == 0


def _isbn13_check_digit(first12: str) -> str:
    # Pesos alternos 1 y 3 (como en los códigos de barras EAN-13).
    total = sum((3 if i % 2 else 1) * int(c) for i, c in enumerate(first12))
    return str((10 - total % 10) % 10)


def normalize_isbn(raw: str | None) -> str | None:
    """Devuelve el ISBN-13 sin guiones ni espacios, o None si no es un ISBN válido.

    Acepta ISBN-10 (libros de antes de 2007) y lo convierte a ISBN-13: se guarda siempre
    en un único formato para que el mismo libro no pueda entrar dos veces.
    """
    value = re.sub(r"[\s-]", "", raw or "").upper()
    if re.fullmatch(r"\d{9}[\dX]", value) and _isbn10_ok(value):
        first12 = "978" + value[:9]
        return first12 + _isbn13_check_digit(first12)
    is_isbn13 = re.fullmatch(r"\d{13}", value) and value.startswith(("978", "979"))
    if is_isbn13 and _isbn13_check_digit(value[:12]) == value[12]:
        return value
    return None


def isbn13_to_isbn10(isbn13: str) -> str | None:
    """El ISBN-10 equivalente, si existe (solo para los que empiezan por 978)."""
    if not isbn13.startswith("978"):
        return None
    first9 = isbn13[3:12]
    check = (11 - sum(w * int(c) for w, c in zip(range(10, 1, -1), first9, strict=True)) % 11) % 11
    return first9 + ("X" if check == 10 else str(check))
