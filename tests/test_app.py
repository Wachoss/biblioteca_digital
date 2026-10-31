def test_catalog_page_lists_books(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "5 libros" in response.text
    assert "Pendiente (2)" in response.text
    assert "<html" in response.text


def test_search_and_filter_in_url(client):
    response = client.get("/", params={"q": "orwell", "status": "leido"})
    assert "1 libro para «orwell» con estado «Leído»" in response.text


def test_empty_or_invalid_status_does_not_filter(client):
    for status in ("", "inventado"):
        assert "5 libros" in client.get("/", params={"status": status}).text


def test_htmx_request_gets_only_the_results(client):
    response = client.get("/", params={"q": "maus"}, headers={"HX-Request": "true"})
    assert "1 libro" in response.text
    assert "<html" not in response.text
    assert response.headers["vary"] == "HX-Request"


def test_htmx_history_restore_gets_full_page(client):
    headers = {"HX-Request": "true", "HX-History-Restore-Request": "true"}
    assert "<html" in client.get("/", headers=headers).text


def test_book_page_uses_large_cover(client):
    book_id = client.get("/api/books", params={"q": "etica"}).json()[0]["id"]
    response = client.get(f"/libros/{book_id}")
    assert "Ética para Amador" in response.text
    assert "https://covers.openlibrary.org/b/id/123-L.jpg" in response.text


def test_missing_book_page_is_html_404(client):
    response = client.get("/libros/999")
    assert response.status_code == 404
    assert "Libro no encontrado" in response.text
    assert response.headers["content-type"].startswith("text/html")


def test_api_lists_books(client):
    books = client.get("/api/books", params={"q": "orwell"}).json()
    assert [b["title"] for b in books] == ["1984", "Rebelión en la granja"]
    assert books[0]["authors"] == ["George Orwell"]
    assert books[0]["status"] == "leido"


def test_api_rejects_invalid_status(client):
    assert client.get("/api/books", params={"status": "inventado"}).status_code == 422


def test_api_missing_book_is_json_404(client):
    response = client.get("/api/books/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Libro no encontrado"}


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}
