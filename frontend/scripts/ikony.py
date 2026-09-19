"""Generuje ikony aplikacji Danaco Nexus (PWA, iOS, Windows) z jednego rysunku.

Logo: litera „N” jako dwa węzły połączone ścieżką (nexus = połączenie) na
fioletowym gradiencie. Rysunek jest powtórzony w SVG (favicon) i w Pillow
(PNG z nadpróbkowaniem 4×). Uruchomienie z katalogu frontend:

    python scripts/ikony.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

PUBLIC = Path(__file__).resolve().parent.parent / "public"
TOP = (139, 124, 246)  # #8b7cf6
BOTTOM = (79, 70, 229)  # #4f46e5
# Punkty litery N w układzie 512×512 i grubości.
POINTS = [(164, 352), (164, 160), (348, 352), (348, 160)]
STROKE = 46
NODE = 34
SCALE = 4

SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#8b7cf6"/>
      <stop offset="1" stop-color="#4f46e5"/>
    </linearGradient>
  </defs>
  <rect width="512" height="512" rx="116" fill="url(#g)"/>
  <path d="M164 352V160l184 192V160" fill="none" stroke="#fff" stroke-width="46"
        stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="164" cy="352" r="34" fill="#fff"/>
  <circle cx="348" cy="160" r="34" fill="#fff"/>
</svg>
"""


def gradient(size: int) -> Image.Image:
    """Gradient ukośny od lewego górnego do prawego dolnego rogu."""
    image = Image.new("RGB", (size, size))
    pixels = image.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            pixels[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM, strict=True))
    return image


def glyph(size: int, scale: float) -> Image.Image:
    """Biała litera-logo (przezroczyste tło) w kwadracie ``size`` przeskalowana o ``scale``."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    factor = size / 512

    def point(x: float, y: float) -> tuple[float, float]:
        return (256 + (x - 256) * scale) * factor, (256 + (y - 256) * scale) * factor

    width = STROKE * scale * factor
    points = [point(x, y) for x, y in POINTS]
    draw.line(points, fill="white", width=round(width), joint="curve")
    for x, y in points:
        radius = width / 2
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="white")
    for x, y in (points[0], points[3]):
        radius = NODE * scale * factor
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="white")
    return layer


def icon(size: int, *, rounded: bool, scale: float = 1.0, transparent_corners: bool = True) -> Image.Image:
    big = size * SCALE
    base = gradient(big).convert("RGBA")
    base.alpha_composite(glyph(big, scale))
    if rounded:
        mask = Image.new("L", (big, big), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, big - 1, big - 1), radius=round(big * 116 / 512), fill=255)
        if transparent_corners:
            base.putalpha(mask)
    return base.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    icons = PUBLIC / "icons"
    icons.mkdir(parents=True, exist_ok=True)
    (PUBLIC / "favicon.svg").write_text(SVG, encoding="utf-8")
    for size in (192, 512):
        icon(size, rounded=True).save(icons / f"icon-{size}.png", optimize=True)
        # Maskable: pełne tło do krawędzi, logo w strefie bezpiecznej (80% średnicy).
        icon(size, rounded=False, scale=0.72).save(icons / f"maskable-{size}.png", optimize=True)
    # iOS zaokrągla ikonę sam i nie obsługuje przezroczystości.
    icon(180, rounded=False, scale=0.86).convert("RGB").save(PUBLIC / "apple-touch-icon.png", optimize=True)
    icon(32, rounded=True).save(icons / "favicon-32.png", optimize=True)
    print("Ikony zapisane w", PUBLIC)


if __name__ == "__main__":
    main()
