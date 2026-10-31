"""Genera los iconos de la PWA y el favicon en app/static/icons/.

    uv run --with pillow python scripts/generar_iconos.py

Pillow no es dependencia de la aplicación: solo hace falta para regenerar los iconos,
así que se pide de paso con `--with` en vez de añadirlo a pyproject.toml.

El dibujo es un libro abierto blanco sobre el azul de Pico.css. Se dibuja a 1024 px y
se reduce a cada tamaño, que es la forma sencilla de tener bordes suaves (antialiasing).
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "app" / "static" / "icons"
BLUE = "#0172ad"  # --pico-primary del tema claro
WHITE = "#ffffff"
BASE = 1024


def draw_book(draw: ImageDraw.ImageDraw, size: int, scale: float) -> None:
    """Libro abierto centrado; `scale` es la fracción del lienzo que ocupa de ancho."""
    w = size * scale
    cx, cy = size / 2, size / 2
    h = w * 0.62
    top, bottom = cy - h / 2, cy + h / 2
    left, right = cx - w / 2, cx + w / 2
    sag = h * 0.08  # el centro del libro queda algo más bajo que las esquinas
    gap = w * 0.025  # separación entre las dos páginas: el lomo
    # Página izquierda y derecha, simétricas.
    draw.polygon(
        [(left, top), (cx - gap, top + sag), (cx - gap, bottom + sag), (left, bottom)], fill=WHITE
    )
    draw.polygon(
        [(right, top), (cx + gap, top + sag), (cx + gap, bottom + sag), (right, bottom)],
        fill=WHITE,
    )
    # Líneas de texto en cada página, en azul.
    line = h * 0.055
    for i in range(4):
        y = top + h * (0.22 + i * 0.17)
        for x0, x1 in ((left + w * 0.07, cx - w * 0.08), (cx + w * 0.08, right - w * 0.07)):
            draw.rounded_rectangle([x0, y, x1, y + line], radius=line / 2, fill=BLUE)


def icon(*, maskable: bool) -> Image.Image:
    img = Image.new("RGBA", (BASE, BASE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if maskable:
        # Android recorta el icono con la forma que quiera (círculo, gota...): el fondo
        # llega hasta el borde y el dibujo cabe en el círculo central del 80 % (zona segura).
        draw.rectangle([0, 0, BASE, BASE], fill=BLUE)
        draw_book(draw, BASE, 0.56)
    else:
        draw.rounded_rectangle([0, 0, BASE - 1, BASE - 1], radius=BASE * 0.22, fill=BLUE)
        draw_book(draw, BASE, 0.7)
    return img


def save(img: Image.Image, name: str, size: int) -> None:
    img.resize((size, size), Image.LANCZOS).save(OUT / name, optimize=True)
    print(f"{name} ({size}×{size})")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    normal, maskable = icon(maskable=False), icon(maskable=True)
    save(normal, "icon-192.png", 192)
    save(normal, "icon-512.png", 512)
    save(maskable, "icon-maskable-512.png", 512)
    # iOS no usa el manifest para el icono y no admite transparencia: usa el de fondo lleno.
    save(maskable.convert("RGB"), "apple-touch-icon.png", 180)
    # favicon.ico lleva dentro varios tamaños; el navegador elige el que necesita.
    normal.save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    print("favicon.ico (16, 32, 48)")


if __name__ == "__main__":
    main()
